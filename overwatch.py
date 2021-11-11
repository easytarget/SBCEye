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
from atexit import register
from signal import signal, SIGTERM, SIGINT, SIGHUP
from multiprocessing import Process, Queue
import schedule
import psutil

# Local classes
from load_config import Settings
from robin import Robin
from httpserver import serve_http
from pinreader import get_pin
from bus_drivers import i2c_setup

# Re-nice to reduce blocking of other processes
os.nice(10)

# The setting class will also process the arguments
settings = Settings()

# Let the console know we are starting
print("Starting OverWatch")
print(f"Working directory: {os.getcwd()}")
print(f'Running: {sys.argv[0]}  @ {settings.my_version}')
print(f"Logging to: {settings.log_file}")

# Logging
handler = RotatingFileHandler(settings.log_file,
        maxBytes=settings.log_file_size,
        backupCount=settings.log_file_count)
logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt=settings.log_date_format,
        handlers=[handler])

# Older scheduler versions can log debug to 'INFO' not 'DEBUG', ignore it.
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.WARN)

# Now we have logging, notify we are starting up
logging.info('')
logging.info(f'Starting overwatch service for: {settings.name}')
logging.info(f'Version: {settings.my_version}')
if settings.default_config:
    logging.warning('Running from default configuration')
    logging.warning('- copy "default.ini" to "config.ini" to customise')

# More meaningful process title
try:
    import setproctitle
    process_name = settings.name.encode("ascii", "ignore").decode("ascii")
    setproctitle.setproctitle(f'overwatch: {process_name}')
except ImportError:
    pass

#
# Import, setup and return hardware drivers, or 'None' if setup fails

disp, bme280 = i2c_setup(settings.have_screen, settings.have_sensor)

if disp:
    disp.contrast(settings.display_contrast)
    disp.invert(settings.display_invert)
    disp.fill(0)  # Blank asap in case we are showing garbage
    disp.show()

if settings.button_out > 0:
    try:
        from RPi import GPIO
    except Exception as e:
        print(e)
        print("ERROR: button & pin control requirements not met, features disabled")
        settings.button_out = 0

#
# Local Classes, Globals

# Override the main data class so it will dump changes to a queue if it exists
# This is used to share data with the seperate display animator process
queue = None
class TheData(dict):
    def __setitem__(self, item, value):
        if queue:
            queue.put([item, value])
        super(TheData, self).__setitem__(item, value)
    # (untested) support deleting items for alerts
    #def __delitem__(self, item, value):
    #    if queue:
    #        queue.put([item], None)
    #    super(TheData, self).__delitem__(item)

# Use a (custom overridden) dictionary to store current readings
data = TheData({})
data["sys-temp"] = 0
data["sys-load"] = 0
data["sys-mem"] = 0
if bme280:
    data["env-temp"] = 0
    data["env-humi"] = 0
    data["env-pres"] = 0
for name,_ in settings.pin_map.items():
    data[f"pin-{name}"] = 0

# time of last data update
data_updated = 0

# Unicode degrees character
DEGREE_SIGN= u'\N{DEGREE SIGN}'

#
# Local functions

def button_control(action="toggle"):
    # Set the controlled pin to a specified state
    if settings.button_out > 0:
        ret = f'{settings.button_name} '
        pin = settings.button_out
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
        state = False
        ret = 'Not supported, no controlled pin number defined'
    update_pins()
    return (ret, state)

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
        if bme280:
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
    for name, pin in settings.pin_map.items():
        this_pin_state =  get_pin(pin)
        if this_pin_state != data[f"pin-{name}"]:
            # Pin has changed state, store new state and log
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
    logging.info(log_line[:-2])
    print(log_line[:-2])

def hourly():
    # Remind everybody we are alive
    myself = os.path.basename(__file__)
    timestamp = time.strftime(settings.time_format)
    print(f'{myself} :: {timestamp}')

def handle_signal(sig, *_):
    # handle common signals
    if DISPLAY:
        # clean up the screen process
        DISPLAY.join()
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
    if bme280:
        logging.info('Environmental sensor configured and enabled')
    elif settings.have_sensor:
        logging.warning('Environmental data configured but no sensor detected: '\
                'Environment status and logging disabled')

    if any(key.startswith('pin-') for key in data):
        logging.info('GPIO monitoring configured and logging enabled')

    for name, pin in settings.pin_map.items():
        data[f'pin-{name}'] = get_pin(pin)
        logging.info(f'{name}: {settings.web_pin_states[data[f"pin-{name}"]]}')

    # Set pin interrupt and output if we have a button and a pin to control
    if settings.button_out > 0:
        GPIO.setmode(GPIO.BCM)  # Use BCM GPIO numbering
        GPIO.setup(settings.button_out, GPIO.OUT)
        logging.info(f'Controllable pin ({settings.button_name}) enabled')
        if settings.button_pin > 0:
            GPIO.setup(settings.button_pin, GPIO.IN)
            # Set up the button pin interrupt
            GPIO.add_event_detect(settings.button_pin,
                    GPIO.RISING, button_interrupt,
                    bouncetime = int(settings.button_hold * 2000))
            logging.info('Button enabled')
        if len(settings.button_url) > 0:
            logging.info(f'Web Button enabled on: /{settings.button_url}')
        print(f'Controllable pin ({settings.button_name}) configured and enabled; '\
                f'(pin={settings.button_pin}, url="{settings.button_url})"')

    # Display animation setup
    if disp:
        from animator import animate
        queue = Queue()
        DISPLAY = Process(target=animate, args=(settings, disp, queue),
                name='overwatch_animator')
        DISPLAY.start()
    else:
        DISPLAY = None
        if settings.have_screen:
            logging.warning('Display configured but did not initialise properly: '\
                    'Display features disabled')

    # Get an initial data reading
    update_data()
    update_pins()

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
    schedule.every().hour.at(":00").do(hourly)
    schedule.every(settings.rrd_interval).seconds.do(update_db)
    if len(settings.pin_map.keys()) > 0:
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
