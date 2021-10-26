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
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
import random
import textwrap
import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
import atexit
import psutil
import schedule

# Local classes
from saver import Saver
from robin import Robin
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
parser.add_argument("--config", "-c",
        help="Config file name, default = config.ini",
        type=str)
parser.add_argument("--datadir", "-d",
        help="Data directory, default = '.'",
        type=str)
args = parser.parse_args()

data_dir = Path(os.path.dirname(os.path.abspath(__file__)))
if args.datadir:
    data_dir = Path(args.datadir)
    if data_dir.is_dir():
        os.chdir(data_dir)
        print(f'Data_dir is: {data_dir}')
    else:
        print(f"Data_dir specified on commandline '{args.datadir}' not found; ignoring")

if args.config:
    config_file = Path(args.config).resolve()
    if config_file.is_file():
        print(f'Using configuration from {config_file}')
    else:
        print(f"Specified configuration file '{config_file}' not found, Exiting.")
        sys.exit()
else:
    config_file = Path('config.ini').resolve()
    if config_file.is_file():
        print(f'Using configuration from {config_file}')
    else:
        config_file = Path('default_config.ini').resolve()
        if config_file.is_file():
            print(f'Using default configuration from {config_file}')
        else:
            print('Cannot find configuration file, exiting')
            sys.exit()

print(f'Config file: (NOT YET FULLY IMPLEMENTED) {config_file}')
print(f"Working directory = {os.getcwd()}")

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
    from RPi import GPIO
    pin_map = s.pin_map
except Exception as e:
    print(e)
    print("GPIO monitorig requirements not met")
    pin_map.clear()

print(pin_map)

# Imports and settings should be OK now, let the console know we are starting
print("Starting OverWatch")

# Start by re-nicing to reduce blocking of other processes
os.nice(10)

# Logging
s.log_file = Path(s.log_file_dir + "/" + s.log_file_name).resolve()
print(f"Logging to: {s.log_file}")
handler = RotatingFileHandler(s.log_file, maxBytes=s.log_file_size, backupCount=s.log_file_count)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt=s.log_date_format, handlers=[handler])

# Older scheduler versions sometimes log actions to 'INFO' not 'DEBUG', spewing debug into the log, sigh..
schedule_logger = logging.getLogger('schedule') # For the scheduler..
schedule_logger.setLevel(level=logging.WARN)    # ignore anything less severe than 'WARN'

# Now we have logging, notify we are starting up
logging.info('')
logging.info(f'Starting overwatch serice for: {s.server_name}')

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
        disp.fill(0)  # Blank as fast in case it is showing garbage
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

# Use a dictionary to store current readings
# start with the standard system readings
data = {
    'sys-temp': 0,
    'sys-load': 0,
    'sys-mem': 0,
}
# add sensor data if present
if HAVE_SENSOR:
    data["env-temp"] = 0
    data["env-humi"] = 0
    data["env-pres"] = 0
# add pins
for name,_ in pin_map.items():
    data[f"pin-{name}"] = 0

# Local functions

# Draw a black filled box to clear the canvas.
def clean():
    draw.rectangle((0,0,span-1,height-1), outline=0, fill=0)

# Put a specific area of the canvas onto display
def show(xpos=0):
    if s.rotate_display:
        disp.image(image.transform((width,height),
                   Image.EXTENT,(xpos,0,xpos+width,height))
                   .transpose(Image.ROTATE_180))
    else:
        disp.image(image.transform((width,height),
                   Image.EXTENT,(xpos,0,xpos+width,height)))
    disp.show()

# Slide the display view across the canvas to animate between screens
def slideout(step=s.slidespeed):
    x_pos = 0
    while x_pos < width + margin:
        show(x_pos)
        x_pos = x_pos + step
    show(width + margin)

def bme_screen(xpos=0):
    # Dictionary with tuples specifying name,format,suffix and Y-position
    items = {
            "env-temp": ('Temp', '.1f', DEGREE_SIGN, 5),
            "env-humi": ('Humi', '.0f', '%', 25),
            "env-pres": ('Pres', '.0f', 'mb', 45),
            }
    for sense,(name,fmt,suffix,ypos) in items.items():
        if sense in data.keys():
            line = f'{name}: {data[sense]:{fmt}}{suffix}'
            draw.text((xpos, ypos), line, font=font, fill=255)

def sys_screen(xpos=0):
    # Dictionary with tuples specifying name,format,suffix and Y-position
    items = {
            "sys-temp": ('CPU', '.1f', DEGREE_SIGN, 5),
            "sys-load": ('Load', '1.2f', '', 25),
            "sys-mem": ('Mem', '.1f', '%', 45),
            }
    for sense,(name,fmt,suffix,ypos) in items.items():
        if sense in data.keys():
            line = f'{name}: {data[sense]:{fmt}}{suffix}'
            draw.text((xpos, ypos), line, font=font, fill=255)

def toggle_button(action="toggle"):
    # Set the first pin in pin_map to a specified state
    if len(pin_map.keys()) > 0:
        name = next(iter(pin_map))
        pin = pin_map[name]
        print(f'toggle_button: {action} on {name}:{pin}')
        ret = f'{name} '
        if action.lower() in ['toggle','invert','button']:
            GPIO.output(pin, not GPIO.input(pin))
            ret += 'Toggled: '
        elif action.lower() in [s.pin_states[1].lower(),'on','true']:
            GPIO.output(pin,True)
            ret += 'Switched: '
        elif action.lower() in [s.pin_states[0].lower(),'off','false']:
            GPIO.output(pin,False)
            ret += 'Switched: '
        elif action.lower() in ['random','easter']:
            GPIO.output(pin,random.choice([True, False]))
            ret += 'Randomly Switched: '
        else:
            return f'I dont know how to "{action}" the {name}!'
        ret += s.pin_states[GPIO.input(pin)]
    else:
        ret = 'Not supported, no pin defined'
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
        data['env-temp'] = bme280.temperature
        data['env-humi'] = bme280.relative_humidity
        data['env-pres'] = bme280.pressure
    data['sys-temp'] = psutil.sensors_temperatures()["cpu_thermal"][0].current
    data['sys-load'] = psutil.getloadavg()[0]
    data['sys-mem'] = psutil.virtual_memory().percent

    # Check if any pins have changed state, and log
    for name, pin in pin_map.items():
        this_pin_state =  GPIO.input(pin)
        if this_pin_state != data[f"pin-{name}"]:
            # Pin has changed state, remember new state and log
            data[f'pin-{name}'] = this_pin_state
            logging.info(f'{name}: {s.pin_states[this_pin_state]}')

def update_db():
    # Runs 3x per minute, updates RRD database and processes screensaver
    rrd.update(data)
    if HAVE_SCREEN:
        screensaver.check()

def log_sensors():
    # Runs on a user defined schedule to dump a line of sensor data in the log
    # Dictionary with tuples specifying name, format and suffix
    loglist = {
            "env-temp": ('Temp', '.1f', DEGREE_SIGN),
            "env-humi": ('Humi', '.0f', '%'),
            "env-pres": ('Pres', '.0f', 'mb'),
            "sys-temp": ('CPU', '.1f', DEGREE_SIGN),
            "sys-load": ('Load', '1.2f', ''),
            "sys-mem": ('Mem', '.1f', '%'),
            }
    log_line = ''
    for sense,(name,fmt,suffix) in loglist.items():
        if sense in data.keys():
            log_line += f'{name}: {data[sense]:{fmt}}{suffix}, '
    print(log_line[:-2])
    logging.info(log_line[:-2])

def scheduler_servicer(seconds=60):
    # Approximate delay while checking for pending scheduled jobs every second
    schedule.run_pending()
    for _ in range(seconds):
        time.sleep(1)
        schedule.run_pending()

def good_bye():
    logging.info('Exiting')
    print('Exit')

# The fun starts here:
if __name__ == '__main__':

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
        screensaver = Saver(s, disp)
        logging.info('Display configured and enabled')
    elif s.have_screen:
        logging.warning('Display configured but not detected:'\
                'Display features disabled')

    # Log sensor status
    if HAVE_SENSOR:
        logging.info('Environmental sensor configured and enabled')
    elif s.have_sensor:
        logging.warning('Environmental data configured but no sensor detected:'\
                'Environment status and logging disabled')

    # GPIO mode and arrays for the pin database path and current status
    if len(pin_map.keys()) > 0:
        GPIO.setmode(GPIO.BCM)  # Set all GPIO pins to BCM GPIO numbering
        GPIO.setwarnings(False) # Dont warn if somethign already using channels

    # Set all gpio pins to 'output' and record their initial status
    # We need to set them as outputs in our context in order to monitor their state.
    # - So long as we do not try to write this will not affect their status,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    for name, pin in pin_map.items():
        GPIO.setup(pin, GPIO.OUT)
        data[f'pin-{name}'] = GPIO.input(pin)
        logging.info(f'{name}: {s.pin_states[data[f"pin-{name}"]]}')
    if any(key.startswith('pin-') for key in data):
        logging.info('GPIO monitoring configured and logging enabled')
    else:
        logging.info("No pins configured for GPIO monitoring, feature disabled")

    # Do we have a button, and a pin to control
    if (len(pin_map.keys()) > 0) and (s.button_pin > 0):
        # Set up the button pin interrupt, if defined
        GPIO.setup(s.button_pin, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(s.button_pin, GPIO.RISING, button_interrupt, bouncetime = 400)
        logging.info('Button enabled')

    # RRD init
    rrd = Robin(s, data)

    # Do an initial, early, data reading to settle sensors etc
    update_data()

    # Start the web server, it will fork into a seperate thread and run continually
    serve_http(s, rrd, data, toggle_button)

    # Exit handler
    atexit.register(good_bye)

    # We got this far... time to start the show
    logging.info("Init complete, starting schedule and entering main loop")

    # Schedule sensor readings, database updates and logging events
    schedule.every(s.sensor_interval).seconds.do(update_data)
    schedule.every(s.rrd_update_interval).seconds.do(update_db)
    if s.log_interval > 0:
        schedule.every(s.log_interval).seconds.do(log_sensors)

    schedule.run_all()  # do the initial log and database update

    # A brief pause for splash
    if HAVE_SCREEN:
        scheduler_servicer(3)

    # Main loop now runs forever
    while True:
        if HAVE_SCREEN:
            if HAVE_SENSOR:
                # Environment Screen
                for this_passp in range(s.passes):
                    clean()
                    bme_screen()
                    show()
                    scheduler_servicer(s.passtime)
                # Update and transition to system screen
                bme_screen()
                sys_screen(width+margin)
                slideout()
                scheduler_servicer(s.passtime)
                # System screen
                for this_pass in range(s.passes):
                    clean()
                    sys_screen()
                    show()
                    scheduler_servicer(s.passtime)
                # Update and transition back to environment screen
                sys_screen()
                bme_screen(width+margin)
                slideout()
                scheduler_servicer(s.passtime)
            else:
                # Just loop refreshing the system screen
                for i in range(s.passes):
                    clean()
                    sys_screen()
                    show()
                    scheduler_servicer(s.passtime)
        else:
            # No screen, so just run schedule jobs in a loop
            scheduler_servicer()
