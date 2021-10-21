#
# User Settings  (with sensible defaults)
#
# Copy this file to `overwatch_settings.py' in your data directory
#  and edit as appropriate.
#
# Default data directory is the overwatch script directory, but this
#  can be overidden on the commandline with the -d option.
# Paths for logging and database can be absolute, or relative to the data directory
#

class Settings:

    # Server name for the Log and Web UI
    server_name = 'Pi OverWatch'

    # Enable/Disable Screen and BME280 sensor
    have_sensor = False
    have_screen = False

    # GPIO:
    # All pins are defined using BCM GPIO numbering
    # https://www.raspberrypi.org/forums/viewtopic.php?t=105200
    # Try running `gpio readall` on the Pi itself ;-)

    # Pin list
    # - List entries consist of ['Name', BCM Pin Number]
    # - The state will be read from the pins at startup and used to track changes
    # - An empty list disables the GPIO features
    # - Example: pin_map = [['Lamp', 16], ['Printer', 20], ['Enclosure', 21]]

    pin_map = []

    # Button pin (set to `0` to disable button)
    # Wnen enabled will always control the 1st entry in the pin list
    button_pin = 0                # BCM Pin Number

    # Web UI
    host = ''                     # Ip address to bind web server to, '' =  bind to all addresses
    port = 7080                   # Port number for web server
    button_path = ''              # Web button url path, leave blank to disable
    time_format = '"%H:%M:%S, %A, %d %B, %Y"'  # time.strftime() formatting

    # Sensor reading update frequency
    sensor_interval = 3           # Seconds

    # Logging
    log_file_path = './logs/'        # Folder must be writable by the OverWatch process
    log_file_name = 'overwatch.log'
    log_interval = 600               # Environmental and system log dump interval (seconds, zero to disable)
    log_file_count = 3               # Maximum number of old logfiles to retain
    log_file_size = 1024*1024        # Maximum size before logfile rolls over
    suppress_glitches=True           # Pin state changes can produce phantom button presses due to crosstalk, ignore them

    # Location for RRD database files (folder must be writable by overwatch process)
    rrd_file_store = "./DB"
    rrd_file_path = "./DB/"
    rrd_file_name = "overwatch.rrd"

    # Default graph durations
    # See https://oss.oetiker.ch/rrdtool/doc/rrdfetch.en.html#TIME%20OFFSET%20SPECIFICATION
    default_graphs = ['3h','1d','3d','1w','1m','3m','1y','3y']
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

#
# End of user config
#
