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

# Default settings are in the file 'default_config.ini'
# Copy this to 'config.ini' and edit as appropriate

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
from atexit import register
import schedule
from subprocess import check_output
from signal import signal, SIGTERM, SIGINT, SIGHUP
from multiprocessing import Process, Queue
import psutil

# Local classes
from load_config import Settings
from robin import Robin
from httpserver import serve_http

my_version = check_output(["git", "describe", "--tags",
        "--always", "--dirty"], cwd=sys.path[0]).decode('ascii').strip()

# Re-nice to reduce blocking of other processes
os.nice(10)

# Let the console know we are starting
print("Starting OverWatch")

# Parse the arguments
parser = argparse.ArgumentParser(
    formatter_class=RawTextHelpFormatter,
    description=textwrap.dedent('''
        All hail the python Overwatch!
        See 'default_settings.py' for more info on how to configure'''),
    epilog=textwrap.dedent('''
        Homepage: https://github.com/easytarget/pi-overwatch
        '''))
parser.add_argument("--config", "-c", type=str,
        help="Config file name, default = config.ini")
parser.add_argument("--version", "-v", action='store_true',
        help="Return Overwatch version string and exit")
args = parser.parse_args()

if args.version:
    # Dump version and quit
    print(f'{sys.argv[0]} {my_version}')
    sys.exit()

print(f"Working directory: {os.getcwd()}")
print(f'Running: {sys.argv[0]}  @ {my_version}')


default_config = False
if args.config:
    config_file = Path(args.config).resolve()
    if config_file.is_file():
        print(f'Using user configuration from {config_file}')
    else:
        print(f"ERROR: Specified configuration file '{config_file}' not found, Exiting.")
        sys.exit()
else:
    config_file = Path('config.ini').resolve()
    if config_file.is_file():
        print(f'Using configuration from {config_file}')
    else:
        config_file = Path(f'{sys.path[0]}/defaults.ini').resolve()
        if config_file.is_file():
            print(f'Using default configuration from {config_file}')
            print(f'\nWARNING: Copy "defaults.ini" to "config.ini" for customisation\n')
            default_config = True
        else:
            print('\nERROR: Cannot find a configuration file, exiting')
            sys.exit()

settings = Settings(config_file)

# Logging
settings.log_file = Path(f'{settings.log_file_dir}/{settings.log_file_name}').resolve()
print(f"Logging to: {settings.log_file}")
handler = RotatingFileHandler(settings.log_file, maxBytes=settings.log_file_size,
            backupCount=settings.log_file_count)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s',
            datefmt=settings.log_date_format, handlers=[handler])

# Older scheduler versions can log debug to 'INFO' not 'DEBUG', ignore it.
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.WARN)

# Now we have logging, notify we are starting up
logging.info('')
logging.info(f'Starting overwatch service for: {settings.name}')
logging.info(f'Version: {my_version}')
if default_config:
    logging.warning('Running from default Configuration!')
    logging.warning('- copy "default.ini" to "config.ini" to customise')

# More meaningful process title
try:
    import setproctitle
    process_name = settings.name.encode("ascii", "ignore").decode("ascii")
    setproctitle.setproctitle(f'overwatch: {process_name}')
except ModuleNotFoundError:
    pass

#
# Import hardware drivers

HAVE_SCREEN = settings.have_screen
HAVE_SENSOR = settings.have_sensor

if HAVE_SCREEN or HAVE_SENSOR:
    # I2C Comms
    try:
        from board import SCL, SDA
        import busio
    except Exception as e:
        print(e)
        print("ERROR: I2C bus requirements not met")
        HAVE_SCREEN = HAVE_SENSOR = False

if HAVE_SCREEN:
    # I2C 128x64 OLED Display
    try:
        import adafruit_ssd1306
    except Exception as e:
        print(e)
        print("ERROR: ssd1306 display requirements not met")
        HAVE_SCREEN = False

if HAVE_SCREEN:
    try:
        from animator import animate
    except Exception as e:
        print(e)
        print("ERROR: Screen animator requirements not met")
        HAVE_SCREEN = False

if HAVE_SENSOR:
    # BME280 I2C Tepmerature Pressure and Humidity sensor
    try:
        import adafruit_bme280
    except Exception as e:
        print(e)
        print("ERROR: BME280 environment sensor requirements not met")
        HAVE_SENSOR = False

pin_map = settings.pin_map
if len(pin_map.keys()) > 0:
    try:
        from RPi import GPIO
    except Exception as e:
        print(e)
        print("ERROR: GPIO monitoring requirements not met, features disabled")
        pin_map.clear()

#
# Initialise the hardware

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
        disp.contrast(settings.display_contrast)
        disp.invert(settings.display_invert)
        disp.fill(0)  # Blank immediately in case it is showing garbage
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

#
# Local Classes, Globals

# Override the main data class so it will dump changes to a queue if it exists
# This is used to share data with the seperate display process
queue = None
class TheData(dict):
    def __setitem__(self, item, value):
        if queue:
            queue.put([item, value])
        super(TheData, self).__setitem__(item, value)
    # we will want to support deleting items for alerts
    #def __delitem__(self, item, value):
    #    if queue:
    #        queue.put([item], None)
    #    super(TheData, self).__delitem__(item)

# Use a dictionary to store current readings
# initialise with standard system data
data = TheData({
    'sys-temp': 0,
    'sys-load': 0,
    'sys-mem': 0,
})
# add sensor data if present
if HAVE_SENSOR:
    data["env-temp"] = 0
    data["env-humi"] = 0
    data["env-pres"] = 0
# add pins as needed
for name,_ in pin_map.items():
    data[f"pin-{name}"] = 0

# time of last data update
data_updated = 0

# Unicode degrees character
DEGREE_SIGN= u'\N{DEGREE SIGN}'

#
# Local functions

def button_control(action="toggle"):
    # Set the first pin in pin_map to a specified state
    if len(pin_map.keys()) > 0:
        name = next(iter(pin_map))
        pin = pin_map[name]
        ret = f'{name} '
        if action.lower() in ['toggle','invert','button']:
            GPIO.output(pin, not GPIO.input(pin))
            ret += 'Toggled: '
        elif action.lower() in [settings.web_pin_states[1].lower(),'on','true']:
            GPIO.output(pin,True)
            ret += 'Switched: '
        elif action.lower() in [settings.web_pin_states[0].lower(),'off','false']:
            GPIO.output(pin,False)
            ret += 'Switched: '
        elif action.lower() in ['random','easter']:
            GPIO.output(pin,random.choice([True, False]))
            ret += 'Randomly Switched: '
        else:
            ret += ': '
        state = GPIO.input(pin)
        ret += settings.web_pin_states[state]
    else:
        name = ''
        state = False
        ret = 'Not supported, no pin defined'
    return (ret, state, name)

def button_interrupt(*_):
    # give a short delay, then re-read input to provide a minimum hold-down time
    # and suppress false triggers from other gpio operations
    time.sleep(settings.button_hold)
    if GPIO.input(settings.button_pin):
        logging.info('Button pressed')
        button_control()

def update_data():
    # Get current environmental and system data, called on demand
    global data_updated
    if (time.time() - data_updated) >= settings.data_interval:
        if HAVE_SENSOR:
            data['env-temp'] = bme280.temperature
            data['env-humi'] = bme280.relative_humidity
            data['env-pres'] = bme280.pressure
            # Failed pressure measurements really foul up the graph, skip
            if data['env-pres'] == 0:
                data['env-pres'] = 'U'
        data['sys-temp'] = psutil.sensors_temperatures()["cpu_thermal"][0].current
        data['sys-load'] = psutil.getloadavg()[0]
        data['sys-mem'] = psutil.virtual_memory().percent
        data_updated = time.time()

def update_pins():
    # Check if any pins have changed state, and log
    for name, pin in pin_map.items():
        this_pin_state =  GPIO.input(pin)
        if this_pin_state != data[f"pin-{name}"]:
            # Pin has changed state, remember new state and log
            data[f'pin-{name}'] = this_pin_state
            logging.info(f'{name}: {settings.web_pin_states[this_pin_state]}')

def update_db():
    # Runs on a scedule, refresh readings and update RRD
    update_data()
    rrd.update(data)

def log_data():
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
    update_data()
    for sense,(name,fmt,suffix) in loglist.items():
        if sense in data.keys():
            log_line += f'{name}: {data[sense]:{fmt}}{suffix}, '
    print(log_line[:-2])
    logging.info(log_line[:-2])

def hourly():
    # Remind everybody we are alive
    myself = os.path.basename(__file__)
    timestamp = time.strftime(settings.time_format)
    print(f'{myself} :: {timestamp}')

def handle_signal(sig, *_):
    # handle common signals
    if screen:
        # clean up the screen process
        screen.join()
    if sig == SIGHUP:
        handle_restart()
    elif sig == SIGINT and settings.debug:
        handle_restart()
    else:
        # calling sys.exit() will invoke handle_exit()
        sys.exit()

def handle_restart():
    # In-Place safe restart (re-reads config)
    logging.info('Safe Restarting')
    print('Restart\n')
    rrd.write_updates()
    os.execv(sys.executable, ['python'] + sys.argv)

def handle_exit():
    rrd.write_updates()
    logging.info('Exiting')
    print('Graceful Exit\n')


# The fun starts here:
if __name__ == '__main__':

    # Log sensor status
    if HAVE_SENSOR:
        logging.info('Environmental sensor configured and enabled')
    elif settings.have_sensor:
        logging.warning('Environmental data configured but no sensor detected: '\
                'Environment status and logging disabled')

    # Display animation setup
    # The animator class will start the screen display and saver
    # as scheduled jobs to run forever
    screen = None
    if HAVE_SCREEN:
        queue = Queue()
        screen = Process(target=animate, args=(settings, disp, queue),
                name='animator')
        screen.start()
    else:
        if settings.have_screen:
            logging.warning('Display configured but did not initialise properly: '\
                    'Display features disabled')

    # Get an initial data reading for system and sensor values
    update_data()

    # GPIO mode and arrays for the pin database path and current status
    if len(pin_map.keys()) > 0:
        GPIO.setmode(GPIO.BCM)  # Set all GPIO pins to BCM GPIO numbering
        GPIO.setwarnings(False) # Dont warn if channels accessed outside this processes

    # Set all gpio pins to 'output' and record their initial status
    # We need to set them as outputs in our context in order to monitor their state.
    # - So long as we do not try to write this will not affect their physical status,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    for name, pin in pin_map.items():
        GPIO.setup(pin, GPIO.OUT)
        data[f'pin-{name}'] = GPIO.input(pin)
        logging.info(f'{name}: {settings.web_pin_states[data[f"pin-{name}"]]}')
    if any(key.startswith('pin-') for key in data):
        logging.info('GPIO monitoring configured and logging enabled')
    elif len(settings.pin_map.keys()) > 0:
        logging.info('GPIO monitoring configured but pin setup failed: '\
                'GPIO features disabled')

    # Enable interrupt if we have a button and a pin to control
    if (len(pin_map.keys()) > 0) and (settings.button_pin > 0):
        # Set up the button pin interrupt, if defined
        GPIO.setup(settings.button_pin, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(settings.button_pin, GPIO.RISING, button_interrupt, bouncetime = 100)
        logging.info('Button enabled')

    # RRD init
    rrd = Robin(settings, data)

    # Start the web server, it will fork into a seperate thread and run continually
    serve_http(settings, rrd, data, (button_control, update_data, update_pins))

    # Exit handlers (needed for rrd data-safe shutdown)
    signal(SIGTERM, handle_signal)
    signal(SIGINT, handle_signal)
    signal(SIGHUP, handle_signal)
    register(handle_exit)

    # Schedule pin monitoring, database updates and logging events
    # Use seperate threads for the different updaters.
    # The display (started in the animate class) runs in the main thread.
    schedule.every().hour.at(":00").do(hourly)
    schedule.every(settings.rrd_interval).seconds.do(update_db)
    if len(pin_map.keys()) > 0:
        schedule.every(settings.pin_interval).seconds.do(update_pins)
    if settings.log_interval > 0:
        schedule.every(settings.log_interval).seconds.do(log_data)

    # We got this far... time to start the show
    logging.info("Init complete, starting schedules and entering service loop")

    # Run all the schedule jobs once, so we have data ready to serve
    schedule.run_all()

    # Start the backup schedule after the run_all()
    rrd.start_backups()

    # Main loop now runs forever while servicing the scheduler
    while True:
        schedule.run_pending()
        time.sleep(1)
