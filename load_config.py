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
        self.name = general["name"]
        self.time_format = general["time_format"]
        self.have_sensor = bool(general["sensor"])
        self.have_screen = bool(general["screen"])

        self.pin_map = {}
        for key in config["pins"]:
            self.pin_map[key] = int(config["pins"][key])

        button = config["button"]
        self.button_pin = int(button["pin"])
        self.button_url = button["url"]
        self.button_hold = float(button["hold"])

        web = config["web"]
        self.web_host = web["host"]
        self.web_port = int(web["port"])
        self.web_sensor_name = web["sensor_name"]
        self.web_pin_states = tuple(web["pin_states"].split(','))

        graph = config["graph"]
        self.graph_durations = graph["durations"].split(',')
        self.graph_wide = int(graph["wide"])
        self.graph_high = int(graph["high"])
        self.graph_line = graph["line"]
        self.graph_area = graph["area"]
        self.graph_comment_l = graph["comment_l"].replace(':','\:')
        self.graph_comment_r = graph["comment_r"].replace(':','\:')
        if not self.graph_comment_l and self.graph_comment_r:
            self.graph_comment_l = " "

        sensor = config["sensor"]
        self.sensor_interval = int(sensor["interval"])

        log = config["log"]
        self.log_file_dir = log["file_dir"]
        self.log_file_name = log["file_name"]
        self.log_interval = int(log["interval"])
        self.log_file_count = int(log["file_count"])
        self.log_file_size = int(log["file_size"]) * 1024
        self.log_date_format = log["date_format"]

        rrd = config["rrd"]
        self.rrd_update_interval = int(rrd["update_interval"])
        self.rrd_file_dir = rrd["file_dir"]
        self.rrd_file_name = rrd["file_name"]
        self.rrd_cache_socket = rrd["cache_socket"]

        display = config["display"]
        self.display_rotate = bool(display["rotate"])
        self.display_contrast = int(display["contrast"])
        self.display_invert = bool(display["invert"])

        saver = config["saver"]
        self.saver_mode = saver["mode"]
        self.saver_on = int(saver["on"])
        self.saver_off = int(saver["off"])

        animate = config["animate"]
        self.animate_passtime = int(animate["passtime"])
        self.animate_passes = int(animate["passes"])
        self.animate_speed = int(animate["speed"])

        print(f"Settings loaded from configuration file successfully")
