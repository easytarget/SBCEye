#
# User Settings  (with sensible defaults)
#

class Settings:

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
    # - The button, if enabled, will always control the 1st entry in the list
    # - An empty list disables the GPIO features
    # - Example: pin_map = [['Lamp', 16], ['Printer', 20], ['Enclosure', 21]]

    pin_map = []

    # Button pin (set to `0` to disable button)
    button_pin = 0                # BCM Pin Number

    # Web UI
    host = ''                     # Ip address to bind web server to, '' =  bind to all addresses
    port = 7080                   # Port number for web server
    server_name = 'Pi OverWatch'  # Used for the title and page heading
    button_path = ''              # Web button url path, leave blank to disable

    # Default graph durations presented to user
    # See https://oss.oetiker.ch/rrdtool/doc/rrdfetch.en.html#TIME%20OFFSET%20SPECIFICATION
    default_graphs = ['3h','1d','3d','1w','1m','3m','1y','3y']
    graph_wide = 1200             # Pixels
    graph_high = 300
    # Other graph attributes
    line_w = 'LINE2:'                      # Line width (See: https://oss.oetiker.ch/rrdtool/doc/rrdgraph_graph.en.html)
    line_c = '#00A0A0'                     # Line color (if you like purple try: line_c = '#A000A0', area_c = '#E0D0E0#FFFFFF:gradheight=0', etc..)
    area_w = 'AREA:'                       # This gives the shadow effect
    area_c = '#D0E0E0#FFFFFF:gradheight=0' # Gradient colors

    # Sensor reading update frequency
    sensor_interval = 3           # Seconds

    # Logging
    log_file = './overwatch.log'  # Folder must be writable by the OverWatch process
    log_interval = 600            # Environmental and system log dump interval (seconds, zero to disable)
    log_lines = 240               # How many lines of logging to show in webui by default
    suppress_glitches=True        # Pin state changes can produce phantom button presses due to crosstalk, ignore them

    # Location for RRD database files (folder must be writable by overwatch process)
    rrd_file_store = "./DB/"

    # Animation
    passtime = 2            # time between display refreshes (seconds)
    passes = 3              # number of refreshes of a screen before moving to next
    slidespeed = 16         # number of rows to scroll on each animation step between screens

    # Display orientation, contrast and burn-in prevention
    rotate_display = True    # Is the display 'upside down'? (generally the ribbon connection from the glass is at the bottom)
    display_invert = False   # Default is light text on dark background
    saver_mode = 'invert'    # Possible values are 'off', 'blank' and 'invert'
    saver_on  = 20           # Start time for screensaver (hour, 24hr clock)
    saver_off =  8           # End time

#
# End of user config
#
