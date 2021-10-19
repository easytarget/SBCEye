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

# Some general functions we will use
import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
import random
import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
import importlib
import atexit
import psutil
import schedule
import textwrap

# Local classes
from saver import Saver
from rrd import Robin
from httpserver import serve_http

# Parse the arguments
parser = argparse.ArgumentParser(
    formatter_class=RawTextHelpFormatter,
    description=textwrap.dedent('''
        All hail the python Overwatch!
        See 'default_settings.py' for more info on how to configure'''),
    epilog=textwrap.dedent('''
        Homepage: https://github.com/easytarget/pi-overwatch
        '''))
parser.add_argument("--datadir", "-d", help="Data directory, will be searched for settings.pl file, default = '.'", type=str)
args = parser.parse_args()

if args.datadir:
    data_dir = Path(args.datadir)
    if data_dir.is_dir():
        sys.path.append(str(data_dir.resolve()))
    else:
        print(f"data_dir specified on commandline ({args.datadir}) not found; ignoring")
else:
    data_dir = Path(os.path.dirname(os.path.abspath(__file__)))

os.chdir(data_dir)
print(f"data directory = {os.getcwd()}")
print(f"PYTHON_PATH = {sys.path}")

try:
    from overwatch_settings import Settings as s
    print("Loaded settings from 'overwatch_settings.py'")
except ModuleNotFoundError:
    print("No user settings found in data directory or PYTHON_PATH, loading from 'default_overwatch_settings.py'")
    from default_overwatch_settings import Settings as s

HAVE_SCREEN = s.have_screen
HAVE_SENSOR = s.have_sensor

if HAVE_SCREEN or HAVE_SENSOR:
    # I2C Comms
    try:
        from board import SCL, SDA
        import busio
    except Exception as e:
        print(e)
        print("I2C bus requirements not met")
        HAVE_SCREEN = HAVE_SENSOR = False

if HAVE_SCREEN:
    # I2C 128x64 OLED Display
    from PIL import Image, ImageDraw, ImageFont
    try:
        import adafruit_ssd1306
    except Exception as e:
        print(e)
        print("ssd1306 display requirements not met")
        HAVE_SCREEN = False

if HAVE_SENSOR:
    # BME280 I2C Tepmerature Pressure and Humidity sensor
    try:
        import adafruit_bme280
    except Exception as e:
        print(e)
        print("BME280 ienvironment sensor requirements not met")
        HAVE_SENSOR = False

# GPIO light control
try:
    import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO
    pin_map = s.pin_map
except Exception as e:
    print(e)
    print("GPIO monitorig requirements not met")
    pin_map = []


# Imports and settings should be OK now, let the console know we are starting
print("Starting OverWatch")

# Start by re-nicing to reduce blocking of other processes
os.nice(10)

# Logging
s.log_file = Path(s.log_file_path + "/" + s.log_file_name).resolve()
print(f"Logging to: {s.log_file}")
handler = RotatingFileHandler(s.log_file, maxBytes=s.log_file_size, backupCount=s.log_file_count)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S', handlers=[handler])

# Older scheduler versions sometimes log actions to 'INFO' not 'DEBUG', spewing debug into the log, sigh..
schedule_logger = logging.getLogger('schedule') # For the scheduler..
schedule_logger.setLevel(level=logging.WARN)    # ignore anything less severe than 'WARN'

# Now we have logging, notify we are starting up
logging.info('')
logging.info("Starting " + s.server_name)

# Initialise the bus, display and sensor
if HAVE_SCREEN or HAVE_SENSOR:
    try:
        # Create the I2C interface object
        i2c = busio.I2C(SCL, SDA)
    except Exception as e:
        print(e)
        print("No I2C bus, display and sensor functions will be disabled")
        HAVE_SCREEN = HAVE_SENSOR = False

if HAVE_SCREEN:
    try:
        # Create the I2C SSD1306 OLED object
        # The first two parameters are the pixel width and pixel height.
        disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
        HAVE_SCREEN = True
        disp.contrast(s.display_contrast)
        disp.invert(s.display_invert)
        disp.fill(0)  # And blank as fast as possible in case it is showing garbage
        disp.show()
        print("We have a ssd1306 display at address " + hex(disp.addr))
    except Exception as e:
        print(e)
        print("We do not have a display")
        HAVE_SCREEN = False

if HAVE_SENSOR:
    try:
        # Create the I2C BME280 sensor object
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
        print("BME280 sensor found with address 0x76")
        HAVE_SENSOR = True
    except Exception as e:
        try:
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
            print("BME280 sensor found with address 0x77")
            HAVE_SENSOR = True
        except Exception as f:
            print(e)
            print(f)
            print("We do not have an environmental sensor")
            HAVE_SENSOR = False

# Unicode degrees character used for display and logging
DEGREE_SIGN= u'\N{DEGREE SIGN}'

# Use a couple of dictionaries to store current readings
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

# Draw a black filled box to clear the canvas.
def clean():
    draw.rectangle((0,0,span-1,height-1), outline=0, fill=0)

# Put a specific area of the canvas onto display
def show(xpos=0):
    if s.rotate_display:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)).transpose(Image.ROTATE_180))
    else:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)))
    disp.show()

# Slide the display view across the canvas to animate between screens
def slideout(step=s.slidespeed):
    x_pos = 0
    while x_pos < width + margin:
        show(x_pos)
        x_pos = x_pos + step
    show(width + margin)

def bme_screen(xpos=0):
    draw.text((xpos,  5), 'Temp : ' + format(envData['temperature'], '.1f') + DEGREE_SIGN,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(envData['humidity'], '.1f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(envData['pressure'], '.0f') + 'mb',  font=font, fill=255)

def sys_screen(xpos=0):
    draw.text((xpos, 5), 'CPU  : ' + format(sysData['temperature'], '.1f') + DEGREE_SIGN,  font=font, fill=255)
    draw.text((xpos, 25), 'Load : ' + format(sysData['load'], '1.2f'), font=font, fill=255)
    draw.text((xpos, 45), 'Mem  : ' + format(sysData['memory'], '.1f') + '%',  font=font, fill=255)

def toggle_button(action="toggle"):
    # Set the first pin to a specified state or read and toggle it..
    if len(pin_map) > 0:
        if action.lower() in ['toggle','flip','invert','mirror','switch']:
            if GPIO.input(pin_map[0][1]):
                GPIO.output(pin_map[0][1],False)
            else:
                GPIO.output(pin_map[0][1],True)
            ret =  pin_map[0][0] + ' Toggled: '
        elif action.lower() in ['on','true','enabled','high','hi']:
            GPIO.output(pin_map[0][1],True)
            ret = pin_map[0][0] + ' Switched: '
        elif action.lower() in ['off','false','disabled','low','lo']:
            GPIO.output(pin_map[0][1],False)
            ret = pin_map[0][0] + ' Switched: '
        elif action.lower() in ['random','easter']:
            pick_one = random.choice([True, False])
            GPIO.output(pin_map[0][1],pick_one)
            ret = pin_map[0][0] + ' Randomly Switched: '
        else:
            return 'I dont know how to "' + action + '" the ' + pin_map[0][0] + '!'
        if GPIO.input(pin_map[0][1]):
            ret += "On"
        else:
            ret += "Off"
    else:
        ret = 'Not supported, no output pin defined'
    return ret

def button_interrupt(*_):
    # give a short delay, then re-read input to provide a minimum hold-down time
    # and suppress false triggers from other gpio operations
    time.sleep(0.1)
    if GPIO.input(s.button_pin):
        logging.info('Button pressed')
        toggle_button()
    elif not s.suppress_glitches:
        logging.info('Button GLITCH')

def update_data():
    # Runs every few seconds to get current environmental and system data
    if HAVE_SENSOR:
        envData['temperature'] = bme280.temperature
        envData['humidity'] = bme280.relative_humidity
        envData['pressure'] = bme280.pressure
    sysData['temperature'] = psutil.sensors_temperatures()["cpu_thermal"][0].current
    sysData['load'] = psutil.getloadavg()[0]
    sysData['memory'] = psutil.virtual_memory().percent

    # Check if any pins have changed state, and log
    for pin in range(len(pin_map)):
        this_pin_state =  GPIO.input(pin_map[pin][1])
        if this_pin_state != pin_state[pin]:
            pin_state[pin] = this_pin_state
            if this_pin_state:
                logging.info(pin_map[pin][0] + ': on')
            else:
                logging.info(pin_map[pin][0] + ': off')

def update_db():
    # Runs 3x per minute, updates RRD database and processes screensaver
    rrd.update(envData, sysData, pin_state)
    if HAVE_SCREEN:
        screensaver.check()

def log_sensors():
    # Runs on a user defined schedule to dump a line of sensor data in the log
    log_line = ''
    if HAVE_SENSOR:
        log_line += 'Temp: ' + format(envData['temperature'], '.1f') + DEGREE_SIGN + ', '
        log_line += 'Humi: ' + format(envData['humidity'], '.0f') + '%, '
        log_line += 'Pres: ' + format(envData['pressure'], '.0f') + 'mb, '
    log_line += 'CPU: ' + format(sysData['temperature'], '.1f') + DEGREE_SIGN + ', '
    log_line += 'Load: ' + format(sysData['load'], '1.2f') + ', '
    log_line += 'Mem: ' + format(sysData['memory'], '.1f') + '%'
    logging.info(log_line)

def schedule_servicing_delay(seconds=60):
    # Approximate delay while checking for pending scheduled jobs every second
    schedule.run_pending()
    for second in range(seconds):
        time.sleep(1)
        schedule.run_pending()

def good_bye():
    logging.info('Exiting')
    print("Exit")

# The fun starts here:
if __name__ == "__main__":

    # RRD init
    rrd = Robin(s, HAVE_SENSOR, pin_map)

    # Display setup
    if HAVE_SCREEN:
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
        screensaver = Saver(disp, s.saver_mode, s.saver_on, s.saver_off, s.display_invert)
        logging.info("Display configured and enabled")
    elif s.have_screen:
        logging.warning("Display configured but not detected: Display features disabled")

    # Log sensor status
    if HAVE_SENSOR:
        logging.info("Environmental sensor configured and enabled")
    elif s.have_sensor:
        logging.warning("Environmental data configured but no sensor detected: Environment status and logging disabled")

    # GPIO mode and arrays for the pin database path and current status
    if len(pin_map) > 0:
        GPIO.setmode(GPIO.BCM)  # Set all GPIO pins to BCM GPIO numbering

    # Set all gpio pins to 'output' and record their initial status
    # We need to set them as outputs in our context in order to monitor their state.
    # - So long as we do not try to write to these pins this will not affect their status,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    pin_state = []
    for pin in range(len(pin_map)):
        GPIO.setup(pin_map[pin][1], GPIO.OUT)
        pin_state.append(GPIO.input(pin_map[pin][1]))
        if pin_state[pin]:
            logging.info(pin_map[pin][0] + ": on")
        else:
            logging.info(pin_map[pin][0] + ": off")
    if len(pin_state) > 0:
        logging.info('GPIO monitoring configured and logging enabled')
    elif len(s.pin_map) > 0:
        logging.warning("GPIO monitoring configured but unable to read pins: GPIO status and logging disabled")

    # Do we have a button, and a pin to control
    if (len(pin_map) > 0) and (s.button_pin > 0):
        # Set up the button pin interrupt, if defined
        GPIO.setup(s.button_pin, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(s.button_pin, GPIO.RISING, button_interrupt, bouncetime = 400)
        logging.info('Button enabled')

    # Do an initial, early, data reading to settle sensors etc
    update_data()

    # Start the web server, it will fork into a seperate thread and run continually
    serve_http(s, rrd, HAVE_SCREEN, HAVE_SENSOR, envData, sysData, pin_state, toggle_button)

    # Exit handler
    atexit.register(good_bye)

    # We got this far... time to start the show
    logging.info("Init complete, starting schedule and entering main loop")

    # Schedule sensor readings, database updates and logging events
    schedule.every(s.sensor_interval).seconds.do(update_data)
    schedule.every(20).seconds.do(update_db)
    if s.log_interval > 0:
        schedule.every(s.log_interval).seconds.do(log_sensors)

    schedule.run_all()  # do the initial log and database update

    # A brief pause for splash
    if HAVE_SCREEN:
        schedule_servicing_delay(3)

    # Main loop now runs forever
    while True:
        if HAVE_SCREEN:
            if HAVE_SENSOR:
                # Environment Screen
                for this_passp in range(s.passes):
                    clean()
                    bme_screen()
                    show()
                    schedule_servicing_delay(s.passtime)
                # Update and transition to system screen
                bme_screen()
                sys_screen(width+margin)
                slideout()
                schedule_servicing_delay(s.passtime)
                # System screen
                for this_pass in range(s.passes):
                    clean()
                    sys_screen()
                    show()
                    schedule_servicing_delay(s.passtime)
                # Update and transition back to environment screen
                sys_screen()
                bme_screen(width+margin)
                slideout()
                schedule_servicing_delay(s.passtime)
            else:
                # Just loop refreshing the system screen
                for i in range(s.passes):
                    clean()
                    sys_screen()
                    show()
                    schedule_servicing_delay(s.passtime)
        else:
            # No screen, so just run schedule jobs in a loop
            schedule_servicing_delay()
