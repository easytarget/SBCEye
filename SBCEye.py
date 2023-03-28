#!/usr/bin/python
'''
SBCEye:
Animate the OLED display attached to my OctoPrint server with bme280 and system data
Show, log and graph the environmental, system and gpio data via a web interface
Give me a on/off button + url to control the bench lights via a GPIO pin

!! DISPLAY, BME280 and GPIO functionality is CURRENTLY Raspberry PI only!
- Needs to be made generic for other architectures

I2C BME280 Sensor and SSD1306 Display:

Note: the sensor and display are optional, if not found their functionality will be
disabled and this will be logged at startup.

Make sure I2C is enabled in 'boot/config.txt' (reboot after editing that file)

- Uncomment: "dtparam=i2c_arm=on", which is the same as you get if enabling I2C
  via the 'Interface Options' in `sudo raspi-config`

- I prefer 'dtparam=i2c_arm=on,i2c_arm_baudrate=400000', to draw the display faster,
  but is more prone to errors from long wires etc.. ymmv

To list all I2C addresses visible on the system run:
$ sudo apt install i2c-tools
$ i2cdetect -y 1`

bme280 I2C address should be 0x76 or 0x77; it will be searched for on these addresses
The SSD1306 I2C address should be automagically found; the driver will bind to the
first matching display
'''

# pragma pylint: disable=logging-fstring-interpolation

# Default settings are in the file 'default_config.ini'
# Copy this to 'config.ini' and edit as appropriate

# Some general functions we will use
import os
import time
import sys
import logging
import random
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from atexit import register
from signal import signal, SIGTERM, SIGINT, SIGHUP
from multiprocessing import Process, Queue
import schedule
import psutil

# Local classes
from load_config import Settings
from robin import Robin
from httpserver import serve_http
from netreader import Netreader
from pinreader import Pinreader
from bus_drivers import i2c_setup

# Re-nice to reduce blocking of other processes
os.nice(10)

# The setting class will also process the arguments
settings = Settings()

# Let the console know we are starting
print("Starting SBCEye")
print(f"Working directory: {os.getcwd()}")
print(f'Running: {sys.argv[0]}  @ {settings.my_version}')
print(f"Logging to: {settings.log_file}")

# Logging
handler = RotatingFileHandler(settings.log_file,
        maxBytes=settings.log_file_size,
        backupCount=settings.log_file_count)
logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt=settings.short_format,
        handlers=[handler])

# Older scheduler versions can log debug to 'INFO' not 'DEBUG', change threshold.
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.WARN)

# Now we have logging, notify we are starting up
logging.info('')
logging.info(f'Starting SBCEye service for: {settings.name}')
logging.info(f'Version: {settings.my_version}')
if settings.default_config:
    logging.warning('Running from default configuration')
    logging.warning('- copy "default.ini" to "config.ini" to customise')

# More meaningful process title
try:
    import setproctitle
    process_name = settings.name.encode("ascii", "ignore").decode("ascii")
    setproctitle.setproctitle(f'SBCEye: {process_name}')
except ImportError:
    pass

# Assume CPU is 1st device in psutils.sensors_temperatures()
cpu_thermal_device = next(iter(psutil.sensors_temperatures()))
logging.info('CPU thermal device detected as: ' + cpu_thermal_device)

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
    except ImportError as e:
        print(e)
        print("ERROR: button & pin control requirements not met, features disabled")
        settings.button_out = 0

#
# Local Classes, Globals

display_queue = None  # will be set during
class TheData(dict):
    '''Override the dictionary class to also send data to the queue for the display'''
    def __setitem__(self, item, value):
        if display_queue:
            display_queue.put([item, value])
        super().__setitem__(item, value)
    def __delitem__(self, item):
        if display_queue:
            display_queue.put([item], None)
        super().__delitem__(item)

# Use a (custom overridden) dictionary to store current readings
data = TheData({})

# Counters used for incremental data need pre-populating
counter = {}
counter["sys-net-io"] = psutil.net_io_counters().bytes_sent \
        + psutil.net_io_counters().bytes_recv
counter["sys-disk-io"] = psutil.disk_io_counters().read_bytes\
        + psutil.disk_io_counters().write_bytes
counter["sys-cpu-int"] = psutil.cpu_stats().soft_interrupts
data["update-time"] = time.time() # time of last update


#
# Local functions

def button_control(action="toggle"):
    '''Set the controlled pin to a specified state'''
    if settings.button_out > 0:
        ret = f'{settings.button_name} '
        pin = settings.button_out
        if action.lower() in ['toggle','invert','button']:
            GPIO.output(pin, not GPIO.input(pin))
            ret += 'Toggled: '
        elif action.lower() in [settings.pin_state_names[1].lower(),'on','true']:
            GPIO.output(pin,True)
            ret += 'Switched: '
        elif action.lower() in [settings.pin_state_names[0].lower(),'off','false']:
            GPIO.output(pin,False)
            ret += 'Switched: '
        elif action.lower() in ['random','easter']:
            GPIO.output(pin,random.choice([True, False]))
            ret += 'Randomly Switched: '
        else:
            ret += ': '
        state = GPIO.input(pin)
        ret += settings.pin_state_names[state]
    else:
        state = False
        ret = 'Not supported, no output pin defined'
    pins.update_pins()
    return (ret, state)

def button_interrupt(*_):
    '''give a short delay, then re-read input to provide a minimum hold-down time
    and suppress false triggers from other gpio operations'''
    time.sleep(settings.button_hold)
    if GPIO.input(settings.button_pin):
        logging.info('Button pressed')
        button_control()

def update_system():
    '''Get current environmental and system data, called on a schedule
    '''
    data['sys-temp'] = psutil.sensors_temperatures()[cpu_thermal_device][0].current
    data['sys-load'] = psutil.getloadavg()[0]
    data["sys-freq"] = psutil.cpu_freq().current
    data['sys-mem'] = psutil.virtual_memory().percent
    data["sys-disk"] = psutil.disk_usage('/').percent
    data["sys-proc"] = len(psutil.pids())
    net_count = psutil.net_io_counters().bytes_sent \
            + psutil.net_io_counters().bytes_recv
    disk_count = psutil.disk_io_counters().read_bytes\
            + psutil.disk_io_counters().write_bytes
    int_count = psutil.cpu_stats().soft_interrupts
    time_period = time.time() - data["update-time"]
    data["update-time"] = time.time()
    data["sys-net-io"] = (net_count - counter["sys-net-io"]) / time_period / 1000
    data["sys-disk-io"] = (disk_count - counter["sys-disk-io"]) / time_period / 1000
    data["sys-cpu-int"] = (int_count - counter["sys-cpu-int"]) / time_period
    counter["sys-net-io"] = net_count
    counter["sys-disk-io"] = disk_count
    counter["sys-cpu-int"] = int_count

def update_sensors():
    '''Get current environmental sensor data
    '''
    if bme280:
        data['env-temp'] = bme280.temperature
        data['env-humi'] = bme280.relative_humidity
        data['env-pres'] = bme280.pressure
        # Failed pressure measurements really foul up the graph, skip
        if data['env-pres'] == 0:
            data['env-pres'] = 'U'

def update_data():
    '''Runs on a scedule, refresh readings and update RRD'''
    update_sensors()
    update_system()
    net.update(data)
    rrd.update(data)

def hourly():
    '''Remind everybody we are alive'''
    myself = os.path.basename(__file__)
    timestamp = time.strftime(settings.long_format)
    uptime = timedelta(seconds=int(time.time() - psutil.boot_time()))
    logging.info(f'{settings.name} :: up {uptime}')
    print(f'{myself} :: {timestamp} :: {settings.name} :: up {uptime}')

def handle_signal(sig, *_):
    '''Handle common signals'''
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
    '''In-Place safe restart (re-reads config)'''
    logging.info('Safe Restarting')
    print('Restart\n')
    rrd.write_updates()
    os.execv(sys.executable, ['python'] + sys.argv)

def handle_exit():
    '''Ensure we write ipending data to the RRD database as we exit'''
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

    # Set button interrupt and output if we have a button and a pin to control
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
        display_queue = Queue()
        DISPLAY = Process(target=animate, args=(settings, disp, display_queue),
                name='sbceye_animator')
        DISPLAY.start()
    else:
        DISPLAY = None
        if settings.have_screen:
            logging.warning('Display configured but did not initialise properly: '\
                    'Display features disabled')

    print('Performing initial data update', end='')
    if settings.net_map:
        print(f' may take up to {settings.net_timeout}s if ping targets are down')
    else:
        print()

    # Populate initial system data
    update_system()

    # Populate initial sensor data
    update_sensors()

    # Network (ping) monitoring
    net = Netreader((settings.net_map, settings.net_timeout), data)

    # GPIO Pin monitoring
    pins = Pinreader((settings.pin_map, settings.pin_state_names), data)

    # RRD init now that the data{} structure is populated
    rrd = Robin(settings, data)

    # Start the web server, it will fork into a seperate thread and run continually
    serve_http(settings, rrd, data, (button_control,))

    # Exit handlers (needed for rrd cache write on shutdown)
    signal(SIGTERM, handle_signal)
    signal(SIGINT, handle_signal)
    signal(SIGHUP, handle_signal)
    register(handle_exit)

    # Schedule pin monitoring, database updates and logging events
    if settings.log_hourly:
        schedule.every().hour.at(":00").do(hourly)
    schedule.every(settings.data_interval).seconds.do(update_data)
    if len(settings.pin_map.keys()) > 0:
        schedule.every(settings.pin_interval).seconds.do(pins.update_pins)

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
