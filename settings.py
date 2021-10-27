#
# Application defaults (sensible)
#
#
import configparser

class Settings:

    # Button pin (set to `0` to disable button)
    # When enabled will always control the 1st entry in the pin list
    button_pin = 27                # BCM Pin Number

    # Web UI
    host = '10.0.0.120'                     # Ip address to bind web server to, '' =  bind to all addresses
    port = 7080                   # Port number for web server
    button_url = 'led'              # Web button url path, leave blank to disable
    sensor_name = 'Room'          # Sensor name (eg; location)
    pin_states = ('Off','On')         # Localisation for pin state (False,True)

    # Sensor reading update frequency
    sensor_interval = 2           # Seconds

    # Logging
    log_file_dir = './logs'        # Folder must be writable by the OverWatch process
    log_file_name = 'overwatch.log'
    log_interval = 600               # Environmental and system log dump interval (seconds, zero to disable)
    log_file_count = 3               # Maximum number of old logfiles to retain
    log_file_size = 1024*1024        # Maximum size before logfile rolls over
    log_date_format = '%d-%m-%Y %H:%M:%S'  # Log line date/timestamp, strftime() format
    suppress_glitches=True           # Pin state changes can produce phantom button presses due to crosstalk, ignore them

    # Location for RRD database files (folder must be writable by overwatch process)
    rrd_update_interval = 15
    rrd_file_dir = './DB'
    rrd_file_name = 'overwatch.rrd'
    rrd_cache_socket = f'{rrd_file_dir}/rrdcache.sock'

    # Default graph durations
    # See https://oss.oetiker.ch/rrdtool/doc/rrdfetch.en.html#TIME%20OFFSET%20SPECIFICATION
    graph_durations = ['3h','1d','3d','1w','1m','3m','1y','3y']
    graph_wide = 1200  # Pixels
    graph_high = 300   # GPIO pin on/off graphs are 1/2 this height
    # Other graph attributes, see: https://oss.oetiker.ch/rrdtool/doc/rrdgraph_graph.en.html
    graph_area = 'AREA:data#D0E0E0#FFFFFF:gradheight=0' # set to '' to disable
    graph_line = 'LINE2:data#00A0A0'  # the '2' is line width in pixels, eg 'LINE5' is wider
    graph_comment = '' # optional notes, copyright, etc. (escape colons ':' with a backslash '\:')

    # Display Animation
    passtime = 2     # time between display refreshes (seconds)
    passes = 3       # number of refreshes of a screen before moving to next
    slidespeed = 16  # number of rows to scroll on each animation step between screens

    # Display orientation, contrast and burn-in prevention
    rotate_display = True    # Is the display 'upside down'? (generally the ribbon connection from the glass is at the bottom)
    display_contrast = 127   # (0-255, default 255) This gives a limited brightness reduction, not full dimming to black
    display_invert = False   # Default is light text on dark background
    saver_mode = 'invert'    # Possible values are 'off', 'blank' and 'invert'
    saver_on  = 20           # Start time for screensaver (hour, 24hr clock)
    saver_off =  8           # End time

    def __init__(self, config_file):
        print()
        print(f'Settings init(config_file = {config_file})')
        config = configparser.RawConfigParser()
        config.optionxform = str
        config.read(config_file)

        # Set attributes from .ini file
        general = config["general"]
        self.server_name = general["server_name"]
        self.time_format = general["time_format"]
        self.have_sensor= general["sensor"]
        self.have_screen = general["screen"]

        self.pin_map = {}
        for key in config["pins"]:
            self.pin_map[key] = int(config["pins"][key])

