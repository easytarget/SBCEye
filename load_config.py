#
# Application defaults (sensible)
#
#
import configparser

class Settings:

    def __init__(self, config_file):
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
        self.button_pin = button.getint("pin")
        self.button_url = button.get("url")
        self.button_hold = button.getfloat("hold")

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
