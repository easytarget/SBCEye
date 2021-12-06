'''Process arguments and load configuration

User can override the standard .ini file on the commandline
Otherwise we use the local config.ini if it exists
If not we use default.ini, which has sensible defaults
'''

import os
import sys
import textwrap
from pathlib import Path
import argparse
from argparse import RawTextHelpFormatter
from subprocess import check_output

import configparser

class Settings:
    '''Provide the settings as a class

    No Methods
    Attributes:
        Basically, look at the class and config.ini file, I'm not going
        to list and describe everything a second time here ;-)
    '''

    def __init__(self):

        self.my_version = check_output(["git", "describe", "--tags",
        "--always", "--dirty"], cwd=sys.path[0]).decode('ascii').strip()

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
            print(f'{sys.argv[0]} {self.my_version}')
            sys.exit()

        self.default_config = False
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
                    print('\nWARNING: Copy "defaults.ini" to "config.ini" for customisation\n')
                    self.default_config = True
                else:
                    print('\nERROR: Cannot find a configuration file, exiting')
                    sys.exit()


        config = configparser.RawConfigParser()
        config.optionxform = str
        config.read(config_file)

        # Set attributes from .ini file

        general = config["general"]
        self.name = general.get("name")
        self.long_format = general.get("long_format")
        self.short_format = general.get("short_format")
        self.have_sensor = general.getboolean("sensor")
        self.have_screen = general.getboolean("screen")
        self.pin_state_names = tuple(general.get("pin_state_names").split(','))
        if self.name == "":
            self.name = f'{os.uname().nodename}'

        web = config["web"]
        self.web_host = web.get("host")
        self.web_port = web.getint("port")
        self.web_sensor_name = web.get("sensor_name")
        self.web_allow_dump = web.getboolean("allow_dump")
        self.web_show_control = web.getboolean("show_control")

        graph = config["graph"]
        self.graph_durations = graph.get("durations").split(',')
        self.graph_wide = graph.getint("wide")
        self.graph_high = graph.getint("high")
        self.graph_line_color = graph.get("line_color")
        self.graph_line_width = graph.get("line_width")
        self.graph_area_color = graph.get("area_color")
        self.graph_area_depth = graph.get("area_depth")
        self.graph_half_height = graph.get("half_height").split(',')

        self.pin_map = {}
        for pin in config["pins"]:
            self.pin_map[pin] = config.getint("pins",pin)

        self.net_map = {}
        for host in config["ping"]:
            self.net_map[host] = config.get("ping",host)

        button = config["button"]
        self.button_out = button.getint("out")
        self.button_pin = button.getint("pin")
        self.button_url = button.get("url")
        self.button_hold = button.getfloat("hold")
        if self.button_out == 0:
            self.button_name = 'Undefined'
        else:
            self.button_name = f'gpio-{self.button_out}'
            for name, pin in self.pin_map.items():
                if pin == self.button_out:
                    self.button_name = name

        intervals = config["intervals"]
        self.pin_interval = intervals.getint("pin")
        self.data_interval = intervals.getint("data")
        self.rrd_interval = intervals.getint("rrd")
        self.log_interval = intervals.getint("log")
        self.net_timeout = min(intervals.getfloat("ping"),self.data_interval-0.5)

        log = config["log"]
        self.log_file_dir = log.get("file_dir")
        self.log_file_name = log.get("file_name")
        self.log_file_count = log.getint("file_count")
        self.log_file_size = log.getint("file_size") * 1024
        self.log_file = Path(
        f'{self.log_file_dir}/{self.log_file_name}').resolve()

        rrd = config["rrd"]
        self.rrd_dir = rrd.get("dir")
        self.rrd_file_name = rrd.get("file_name")
        self.rrd_backup_count = rrd.getint("backup_count")
        self.rrd_backup_age = int(abs(rrd.getfloat("backup_age")) * 86400)
        self.rrd_backup_time = rrd.get("backup_time")

        display = config["display"]
        self.display_rotate = display.getboolean("rotate")
        self.display_contrast = display.getint("contrast")
        self.display_invert = display.getboolean("invert")

        saver = config["saver"]
        self.saver_mode = saver.get("mode")
        self.saver_on = saver.getint("on")
        self.saver_off = saver.getint("off")

        animate = config["animate"]
        self.animate_passtime = animate.getint("passtime")
        self.animate_passes = animate.getint("passes")
        self.animate_speed = animate.getint("speed")

        self.cam_url = None
        if "webcam" in config:
            cam = config["webcam"]
            self.cam_url = cam.get("url")
            self.cam_width = cam.getint("width", 50)

        # Optional [DEBUG] section can be enabled
        #  If this section is present it changes the operation of
        #  SIGINT (eg Ctrl-c) to restart the service, instead of exiting
        # Currently has no other configurable items
        if "debug" in config:
            self.debug = True
        else:
            self.debug = False

        print("Settings loaded from configuration file successfully")
