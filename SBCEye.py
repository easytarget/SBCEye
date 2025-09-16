#!/usr/bin/python
'''
SBCEye:
Animate the OLED display attached to my OctoPrint server with bme280 and system data
Show, log and graph the environmental, system and gpio data via a web interface

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
from gpioreader import GPIOHandler
from i2c_bus import i2c_setup
from bme_sensor import bme_setup
from oled_display import oled_setup

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

# Older scheduler versions might log debug at wrong level, change threshold.
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

i2c = i2c_setup(settings)

#
# Local Classes, Globals

# We override the dictionary class so that every time an item is
# modified it sends a a message to the display queue.
# This allows the display to run in a seperate process while keeping
# it's local data copy updated in real-time.
# The queue is initially disabled (type: None), and assigned as a
# queue object only if the display is enabled and detected.
display_queue = None
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

# Use this overridden dictionary to store current readings
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

def update_system():
    '''Get current environmental and system data, called on a schedule'''
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
    '''Get current environmental sensor data'''
    if bme:
        bme.update_sensor()
        data['env-temp'] = bme.temperature
        data['env-humi'] = bme.humidity
        data['env-pres'] = bme.pressure
        # Failed pressure measurements really foul up the graph, skip
        if data['env-pres'] == 0:
            data['env-pres'] = 'U'

def update_data():
    '''Runs on a scedule, refresh readings and update RRD'''
    update_sensors()
    update_system()
    net.update(data)
    rrd.update(data)

def daily():
    '''Remind everybody we are alive'''
    myself = os.path.basename(__file__)
    timestamp = time.strftime(settings.long_format)
    uptime = timedelta(seconds=int(time.time() - psutil.boot_time()))
    logging.info(f'{settings.name} :: system uptime {uptime}')
    print(f'{myself} :: {timestamp} :: {settings.name} :: system uptime {uptime}',flush=True)

def handle_signal(sig, *_):
    '''Handle common signals'''
    if DISPLAY:
        # clean up the display process
        DISPLAY.join()
    if sig == SIGHUP:
        handle_restart()
    elif sig == SIGINT and settings.debug_sigint:
        handle_restart()
    else:
        # calling sys.exit() will invoke handle_exit()
        sys.exit()

def handle_restart():
    '''In-Place safe restart (re-reads config)'''
    logging.info('Safe Restarting')
    print('Restart\n',flush=True)
    rrd.write_updates()
    os.execv(sys.executable, ['python'] + sys.argv)

def handle_exit():
    '''Ensure we write ipending data to the RRD database as we exit'''
    rrd.write_updates()
    logging.info('Exiting')
    print('Graceful Exit\n',flush=True)


# The fun starts here:
if __name__ == '__main__':

    # Environmental sensor
    bme = bme_setup(i2c, settings) if i2c else None
    if bme:
        logging.info('Environmental sensor configured and enabled')
    elif settings.have_sensor:
        logging.warning('Environmental data configured but no sensor available: '\
                'Environment status and logging disabled')

    # Display animation setup
    disp = oled_setup(i2c, settings) if i2c else None
    if disp:
        # display initialisation does a 'clear()' and 'show()'
        disp.contrast(settings.display_contrast)

        from animator import animate
        display_queue = Queue()
        DISPLAY = Process(target=animate, args=(settings, disp, display_queue),
                name='sbceye_animator')
        DISPLAY.start()
    else:
        DISPLAY = None
        if settings.have_display:
            logging.warning('Display configured but did not initialise properly: '\
                    'Display features disabled')

    print('Performing initial data update', end='')
    if settings.netlist:
        print(f' (may take up to {settings.net_timeout}s if ping targets are down)')
    else:
        print()

    # Populate initial system data
    update_system()

    # Populate initial sensor data
    update_sensors()

    # GPIO pin monitoring
    gpio = GPIOHandler(settings.pinlist, settings.outlist, data)

    # Network (ping) monitoring
    net = Netreader((settings.netlist, settings.net_timeout), data)

    # RRD init now that the data{} structure is populated
    rrd = Robin(settings, data)

    # Start the web server, it will fork into a seperate thread and run continually
    serve_http(settings, rrd, gpio.pins, data)

    # Exit handlers (needed for rrd cache write on shutdown)
    signal(SIGTERM, handle_signal)
    signal(SIGINT, handle_signal)
    signal(SIGHUP, handle_signal)
    register(handle_exit)

    # Schedule pin monitoring, database updates and logging events
    schedule.every(settings.data_interval).seconds.do(update_data)
    if gpio.available:
        schedule.every(settings.pin_interval).seconds.do(gpio.update)
    if settings.log_daily:
        schedule.every().day.at("00:00").do(daily)

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
