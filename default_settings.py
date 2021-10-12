#
# User Settings  (with sensible defaults)
#

class settings:

    # Enable/Disable Screen and BME280 sensor
    haveSensor = False
    haveScreen = False

    # GPIO:
    # All pins are defined using BCM GPIO numbering
    # https://www.raspberrypi.org/forums/viewtopic.php?t=105200
    # Try running `gpio readall` on the Pi itself ;-)

    # Pin list
    # - List entries consist of ['Name', BCM Pin Number]
    # - The state will be read from the pins at startup and used to track changes
    # - The button, if enabled, will always control the 1st entry in the list
    # - An empty list disables the GPIO features
    # - Example: pinMap = [['Lamp', 16], ['Printer', 20], ['Enclosure', 21]]

    pinMap = []

    # Button pin (set to `0` to disable button)
    buttonPin = 0                # BCM Pin Number

    # Web UI
    host = ''                    # Ip address to bind web server to, '' =  bind to all addresses
    port = 7080                  # Port number for web server
    serverName = 'Pi OverWatch'  # Used for the title and page heading
    buttonPath = ''              # Web button url path, leave blank to disable

    # Default graph durations presented to user
    # See https://oss.oetiker.ch/rrdtool/doc/rrdfetch.en.html#TIME%20OFFSET%20SPECIFICATION
    graphDefaults = ['3h','3d','1w','1m','3m','1y','3y']
    graphWide = 1200             # Pixels
    graphHigh = 300
    # Other graph attributes 
    lineW = 'LINE2:'                      # Line width (See: https://oss.oetiker.ch/rrdtool/doc/rrdgraph_graph.en.html)
    lineC = '#A000A0'                     # Line color (I like purple..)
    areaW = 'AREA:'                       # This gives the shadow effect
    areaC = '#E0D0E0#FFFFFF:gradheight=0' # More purple..

    # Sensor reading update frequency
    sensorInterval = 3           # Seconds

    # Logging
    logFile = './overwatch.log'  # Folder must be writable by the OverWatch process
    logInterval = 600            # Environmental and system log dump interval (seconds, zero to disable)
    logLines = 240               # How many lines of logging to show in webui by default
    suppressGlitches=True        # Pin state changes can produce phantom button presses due to crosstalk, ignore them

    # Location for RRD database files (folder must be writable by overwatch process)
    rrdFileStore = "./DB/"

    # Animation
    passtime = 2            # time between display refreshes (seconds)
    passes = 3              # number of refreshes of a screen before moving to next
    slidespeed = 16         # number of rows to scroll on each animation step between screens

    # Display orientation, contrast and burn-in prevention
    rotateDisplay = True    # Is the display 'upside down'? (generally the ribbon connection from the glass is at the bottom)
    displayContrast = 127   # (0-255, default 255) This gives a limited brightness reduction, not full dimming to black 
    displayInvert = False   # Default is light text on dark background
    saverMode = 'invert'    # Possible values are 'off', 'blank' and 'invert'
    saverOn  = 20           # Start time for screensaver (hour, 24hr clock)
    saverOff =  8           # End time

#
# End of user config
#
