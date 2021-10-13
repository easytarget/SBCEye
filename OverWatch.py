#!/usr/bin/python

# Pi Overwatch:
# Animate the SSD1306 display attached to my OctoPrint server with bme280 and system data
# Show, log and graph the environmental, system and gpio data via a web interface
# Give me a on/off button + url to control the bench lights via a GPIO pin

# I2C BME280 Sensor and SSD1306 Display:
#
# Note: the sensor and display are optional, if not found their functionality will be disabled and this will be logged at startup.
#
# Make sure I2C is enabled in 'boot/config.txt' (reboot after editing that file)
# Uncomment: "dtparam=i2c_arm=on", which is the same as you get if enabling I2C via the 'Interface Options' in `sudo raspi-config`
# I prefer 'dtparam=i2c_arm=on,i2c_arm_baudrate=400000', to draw the display faster, but is more prone to errors from long wires etc.. ymmv.

# To list all I2C addresses visible on the system run: `i2cdetect -y 1` (`sudo apt install i2c-tools`)
# bme280 I2C address should be 0x76 or 0x77 (this is selectable via a jumper) and we will search for it there
# The SSD1306 I2C address should be automagically found; the driver will bind to the first matching display

# Default settings are in the file 'settings_default.py'
# Copy this to 'settings.py' and edit as appropriate

try:
    print("Loading settings from user settings file")
    from settings import settings as s
except (ModuleNotFoundError):
    print("No user settings found, loading from default settings file")
    from default_settings import settings as s

# Local classes
from saver import saver
from rrd import rrd
from httpserver import ServeHTTP

# Some general functions we will use
import os
import time
import datetime
import subprocess

# System monitoring tools
import psutil

haveScreen = s.haveScreen
haveSensor = s.haveSensor

if haveScreen or haveSensor:
    # I2C Comms
    try:
        from board import SCL, SDA
        import busio
    except Exception as e:
        print(e)
        print("I2C bus requirements not met")
        haveScreen = haveSensor = False

if haveScreen:
    # I2C 128x64 OLED Display
    from PIL import Image, ImageDraw, ImageFont
    try:
        import adafruit_ssd1306
    except Exception as e:
        print(e)
        print("ssd1306 display requirements not met")
        haveScreen = False

if haveSensor:
    # BME280 I2C Tepmerature Pressure and Humidity sensor
    try:
        import adafruit_bme280
    except Exception as e:
        print(e)
        print("BME280 ienvironment sensor requirements not met")
        haveSensor = False

# GPIO light control
import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO

# Scheduler and Logging
import schedule
import logging
from logging.handlers import RotatingFileHandler

# Exit Handler
import atexit

# Let the console know we are starting
print("Starting OverWatch")

# Logging 
handler = RotatingFileHandler(s.logFile, maxBytes=1024*1024, backupCount=2)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S', handlers=[handler])
# Older scheduler versions sometimes log actions to 'INFO' not 'DEBUG', spewing debug into the log, sigh..
schedule_logger = logging.getLogger('schedule')  # Oi! Schedule!
schedule_logger.setLevel(level=logging.WARN)     # Stop it.

# Now we have logging, notify we are starting up
logging.info('')
logging.info("Starting " + s.serverName)

# Initialise the bus, display and sensor
if haveScreen or haveSensor:
    try:
        # Create the I2C interface object
        i2c = busio.I2C(SCL, SDA)
    except Exception as e:
        print(e)
        print("No I2C bus, display and sensor functions will be disabled")
        haveScreen = haveSensor = False

if haveScreen:
    try:
        # Create the I2C SSD1306 OLED object
        # The first two parameters are the pixel width and pixel height.
        disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
        haveScreen = True
        disp.contrast(s.displayContrast)
        disp.invert(s.displayInvert)
        disp.fill(0)  # And blank as fast as possible in case it is showing garbage
        disp.show()
        print("We have a ssd1306 display at address " + hex(disp.addr))
    except Exception as e:
        print(e)
        print("We do not have a display")
        haveScreen = False

if haveSensor:
    try:
        # Create the I2C BME280 sensor object
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
        print("BME280 sensor found with address 0x76")
        haveSensor = True
    except Exception as e:
        try:
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
            print("BME280 sensor found with address 0x77")
            haveSensor = True
        except Exception as f:
            print(e)
            print(f)
            print("We do not have an environmental sensor")
            haveSensor = False

# GPIO mode and arrays for the pin database path and current status
if (len(s.pinMap) > 0):
    GPIO.setmode(GPIO.BCM)  # Set all GPIO pins to BCM GPIO numbering

# Display setup
if haveScreen:
    # Image canvas
    margin = 20           # Space between the screens while transitioning
    width  = disp.width
    span   = width*2 + margin
    height = disp.height

    # Create image canvas (with mode '1' for 1-bit color)
    image = Image.new("1", (span, height))

    # Get drawing object so we can easily draw on canvas.
    draw = ImageDraw.Draw(image)

    # LiberationMono-Regular : nice font that looks clear on the small display
    # This font is located in: /usr/share/fonts/truetype/liberation/ on Raspian.
    # If you get an error that it is not present, install it with:
    #   sudo apt install fonts-liberation
    font = ImageFont.truetype('LiberationMono-Regular.ttf', 16)

    # Splash!
    draw.text((10, 10), 'Over-',  font=font, fill=255)
    draw.text((28, 28), 'Watch',  font=font, fill=255)
    disp.show()

    # Start saver
    screensaver = saver(disp, s.saverMode, s.saverOn, s.saverOff, s.displayInvert)

# Unicode degrees character used for display and logging
degree_sign= u'\N{DEGREE SIGN}'

# RRD init
rrd = rrd(s.rrdFileStore, haveSensor, s.pinMap)

# Use a couple of dictionaries to store latest readings
sysData = {
    'temperature': 0,
    'load': 0,
    'memory': 0
}
envData = {
    'temperature': 0,
    'humidity': 0,
    'pressure':0
    }

# Local functions

def clean():
    # Draw a black filled box to clear the canvas.
    draw.rectangle((0,0,span-1,height-1), outline=0, fill=0)

def show(xpos=0):
    # Put a specific area of the canvas onto display
    if s.rotateDisplay:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)).transpose(Image.ROTATE_180))
    else:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)))
    disp.show()

def slideout(step=s.slidespeed):
    # Slide the display view across the canvas to animate between screens
    x = 0
    while x < width + margin:
        show(x)
        x = x + step
    show(width + margin)

def bmeScreen(xpos=0):
    draw.text((xpos,  5), 'Temp : ' + format(envData['temperature'], '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(envData['humidity'], '.1f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(envData['pressure'], '.0f') + 'mb',  font=font, fill=255)

def sysScreen(xpos=0):
    draw.text((xpos, 5), 'CPU  : ' + format(sysData['temperature'], '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Load : ' + format(sysData['load'], '1.2f'), font=font, fill=255)
    draw.text((xpos, 45), 'Mem  : ' + format(sysData['memory'], '.1f') + '%',  font=font, fill=255)

def toggleButton(action="toggle"):
    # Set the first pin to a specified state or read and toggle it..
    if (len(s.pinMap) > 0):
        if (action == 'toggle'):
            if (GPIO.input(s.pinMap[0][1]) == True):
                GPIO.output(s.pinMap[0][1],False)
                return s.pinMap[0][0] + ' Toggled: off'
            else:
                GPIO.output(s.pinMap[0][1],True)
                return s.pinMap[0][0] + ' Toggled: on'
        elif (action == 'on'):
            GPIO.output(s.pinMap[0][1],True)
            return s.pinMap[0][0] + ' Switched: on'
        elif (action == 'off'):
            GPIO.output(s.pinMap[0][1],False)
            return s.pinMap[0][0] + ' Switched: off'
        else:
            return 'I dont know how to "' + action + '" the ' + s.pinMap[0][0] + '!'
    else:
        return 'Not supported, no output pin defined'

def buttonInterrupt(channel):
    # give a short delay, then re-read input to provide a minimum hold-down time
    # and suppress false triggers from other gpio operations
    time.sleep(0.1)
    if (GPIO.input(s.buttonPin) == True):
        logging.info('Button pressed')
        toggleButton()
    elif (not s.suppressGlitches):
        logging.info('Button GLITCH')

def updateData():
    # Runs every few seconds to get current environmental and system data
    if haveSensor:
        envData['temperature'] = bme280.temperature
        envData['humidity'] = bme280.relative_humidity
        envData['pressure'] = bme280.pressure
    sysData['temperature'] = psutil.sensors_temperatures()["cpu_thermal"][0].current
    sysData['load'] = psutil.getloadavg()[0]
    sysData['memory'] = psutil.virtual_memory().percent

    # Check if any pins have changed state, and log
    for i in range(len(s.pinMap)):
        thisPinState =  GPIO.input(s.pinMap[i][1])
        if (thisPinState != pinState[i]):
            pinState[i] = thisPinState
            if (thisPinState):
                logging.info(s.pinMap[i][0] + ': on')
            else:
                logging.info(s.pinMap[i][0] + ': off')

def updateDB():
    # Runs 3x per minute, updates RRD database and processes screensaver
    rrd.update(envData, sysData, pinState)
    if haveScreen:
        screensaver.check()

def logSensors():
    # Runs on a user defined schedule to dump a line of sensor data in the log
    logLine = ''
    if haveSensor:
        logLine += 'Temp: ' + format(envData['temperature'], '.1f') + degree_sign + ', '
        logLine += 'Humi: ' + format(envData['humidity'], '.0f') + '%, '
        logLine += 'Pres: ' + format(envData['pressure'], '.0f') + 'mb, '
    logLine += 'CPU: ' + format(sysData['temperature'], '.1f') + degree_sign + ', '
    logLine += 'Load: ' + format(sysData['load'], '1.2f') + ', '
    logLine += 'Mem: ' + format(sysData['memory'], '.1f') + '%'
    logging.info(logLine)

def scheduleServicingDelay(seconds=60):
    # Approximate delay while checking for pending scheduled jobs every second
    schedule.run_pending()
    for t in range(seconds):
        time.sleep(1)
        schedule.run_pending()

def goodBye():
    logging.info('Exiting')

# The fun starts here:
if __name__ == "__main__":
    # Start by re-nicing to reduce blocking of other processes
    os.nice(10)

    # Log screen and sensor status
    if haveScreen:
        logging.info("Display configured and enabled")
    elif s.haveScreen:
        logging.warning("Display configured but not detected: Display features disabled")
    if haveSensor:
        logging.info("Environmental sensor configured and enabled")
    elif s.haveSensor:
        logging.warning("Environmental data configured but no sensor detected: Environment status and logging disabled")

    # Set all gpio pins to 'output' and record their initial status
    # We need to set them as outputs in our context in order to monitor their state.
    # - So long as we do not try to write to these pins this will not affect their status,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    pinState = []
    for i in range(len(s.pinMap)):
        GPIO.setup(s.pinMap[i][1], GPIO.OUT)
        pinState.append(GPIO.input(s.pinMap[i][1]))
        if (pinState[i]):
            logging.info(s.pinMap[i][0] + ": on")
        else:
            logging.info(s.pinMap[i][0] + ": off")
    if (len(pinState) > 0)
        logging.info('GPIO configured and logging enabled')

    # Do we have a button, and a pin to control
    if (len(s.pinMap) > 0) and (s.buttonPin > 0):
        # Set up the button pin interrupt, if defined
        GPIO.setup(s.buttonPin, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(s.buttonPin, GPIO.RISING, buttonInterrupt, bouncetime = 400)
        logging.info('Button enabled')

    # Do an initial, early, data reading to settle sensors etc
    updateData()

    # Start the web server, it will fork into a seperate thread and run continually
    ServeHTTP(s, rrd, haveScreen, haveSensor, envData, sysData, pinState, toggleButton)

    # Exit handler
    atexit.register(goodBye)

    # We got this far... time to start the show
    logging.info("Init complete, starting schedule and entering main loop")

    # Schedule sensor readings, database updates and logging events
    schedule.every(s.sensorInterval).seconds.do(updateData)
    schedule.every(20).seconds.do(updateDB)
    if (s.logInterval > 0):
        schedule.every(s.logInterval).seconds.do(logSensors)

    schedule.run_all()  # do the initial log and database update

    # A brief pause for splash
    if haveScreen:
        scheduleServicingDelay(3)

    # Main loop now runs forever
    while True:
        if haveScreen:
            if haveSensor:
                # Environment Screen
                for i in range(s.passes):
                    clean()
                    bmeScreen()
                    show()
                    scheduleServicingDelay(s.passtime)
                # Update and transition to system screen
                bmeScreen()
                sysScreen(width+margin)
                slideout()
                scheduleServicingDelay(s.passtime)
                # System screen
                for i in range(s.passes):
                    clean()
                    sysScreen()
                    show()
                    scheduleServicingDelay(s.passtime)
                # Update and transition back to environment screen
                sysScreen()
                bmeScreen(width+margin)
                slideout()
                scheduleServicingDelay(s.passtime)
            else:
                # Just loop refreshing the system screen
                for i in range(s.passes):
                    clean()
                    sysScreen()
                    show()
                    scheduleServicingDelay(s.passtime)
        else:
            # No screen, so just run schedule jobs in a loop
            scheduleServicingDelay()
