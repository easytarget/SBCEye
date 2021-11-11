'''Process arguments and load configuration

User can override the standard .ini file on the commandline
Otherwise we use the local config.ini if it exists
If not we use default.ini, which has sensible defaults
'''

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
        self.time_format = general.get("time_format")
        self.have_sensor = general.getboolean("sensor")
        self.have_screen = general.getboolean("screen")

        web = config["web"]
        self.web_host = web.get("host")
        self.web_port = web.getint("port")
        self.web_sensor_name = web.get("sensor_name")
        self.web_pin_states = tuple(web.get("pin_states").split(','))
        self.web_allow_dump = web.getboolean("allow_dump")
        self.web_show_control = web.getboolean("show_control")

        graph = config["graph"]
        self.graph_durations = graph.get("durations").split(',')
        self.graph_wide = graph.getint("wide")
        self.graph_high = graph.getint("high")
        self.graph_line = graph.get("line")
        self.graph_area = graph.get("area")
        self.graph_comment_l = graph.get("comment_l").replace(':',r'\:')
        self.graph_comment_r = graph.get("comment_r").replace(':',r'\:')
        if not self.graph_comment_l and self.graph_comment_r:
            self.graph_comment_l = " "

        self.pin_map = {}
        for key in config["pins"]:
            self.pin_map[key] = config.getint("pins",key)

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

        interval = config["interval"]
        self.pin_interval = interval.getint("pin")
        self.data_interval = interval.getint("data")
        self.rrd_interval = interval.getint("rrd")
        self.log_interval = interval.getint("log")

        log = config["log"]
        self.log_file_dir = log.get("file_dir")
        self.log_file_name = log.get("file_name")
        self.log_file_count = log.getint("file_count")
        self.log_file_size = log.getint("file_size") * 1024
        self.log_date_format = log.get("date_format")
        self.log_file = Path(
        f'{self.log_file_dir}/{self.log_file_name}').resolve()

        rrd = config["rrd"]
        self.rrd_dir = rrd.get("dir")
        self.rrd_file_name = rrd.get("file_name")
        self.rrd_cache_age = abs(rrd.getint("cache_age"))
        self.rrd_backup_count = rrd.getint("backup_count")
        self.rrd_backup_age = int(abs(rrd.getfloat("backup_age")) * 86400)
        self.rrd_backup_time = rrd.get("backup_time")

        display = config["display"]
        self.display_rotate = display.getboolean("rotate")
        self.display_contrast = display.getint("contrast")
        self.display_invert = display.getboolean("invert")
        self.display_screens = display.get("screens").split(',')

        saver = config["saver"]
        self.saver_mode = saver.get("mode")
        self.saver_on = saver.getint("on")
        self.saver_off = saver.getint("off")

        animate = config["animate"]
        self.animate_passtime = animate.getint("passtime")
        self.animate_passes = animate.getint("passes")
        self.animate_speed = animate.getint("speed")

        if "debug" in config:
            self.debug = True
        else:
            self.debug = False

        print("Settings loaded from configuration file successfully")
