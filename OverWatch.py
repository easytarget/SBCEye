#! /usr/bin/python
# Pi Overwatch:
# Animate the SSD1306 display attached to my OctoPrint server with bme280 and system data
# Show, log and graph the environmental, system and gpio data via a web interface
# Give me a on/off button + url to control the bench lights via a GPIO pin

#
# User Settings  (with sensible defaults)
#

# I2C Sensor and Display:
# Make sure I2C is enabled in 'boot/config.txt' (reboot after editing that file)
# Uncomment: "dtparam=i2c_arm=on", which is the same as you get if enabling I2C via the 'Interface Options' in `sudo raspi-config` 
# I prefer 'dtparam=i2c_arm=on,i2c_arm_baudrate=400000', to draw the display faster, but is more prone to errors from long wires etc.. ymmv.

# To list all I2C addresses visible on the system run: `i2cdetect -y 1` (`sudo apt install i2c-tools`)
# bme280 I2C address (should not change)
bme280_address = 0x76
# The SSD1306 I2C address should be automagically found; the driver will bind to the first matching display

# GPIO:
# All pins are defined using BCM GPIO numbering
# https://www.raspberrypi.org/forums/viewtopic.php?t=105200
# Try running `gpio readall` on the Pi itself ;-)

# Button pin (set to `0` to disable button)
button_PIN = 0         # BCM Pin Number

# Pin list
# - List entries consist of ['Name', BCM Pin Number]
# - The state will be read from the pins at startup and used to track changes
# - The button, if enabled, will always control the 1st entry in the list
# - An empty list disables the GPIO features
# - Example: pinMap = [['Lamp', 16], ['Printer', 20], ['Enclosure', 21]]

pinMap = []

# Web UI
host = ''                          # Ip address to bind web server to, '' =  bind to all addresses
port = 7080                        # Port number for web server
serverName = 'Pi OverWatch'        # Used for the title and page heading
buttonPath = ''                    # Web button url path, leave blank to disable

# Sensor reading update frequency
sensorInterval = 3                 # Seconds, Minimum 1

# Logging
logFile = './overwatch.log'        # Folder must be writable by the OverWatch process
logInterval = 10                   # Environmental and system log interval (seconds, zero to disable)
logLines = 240                     # How many lines of logging to show in webui by default
suppressGlitches=True              # Pin interrupts can produce phantom button presses due to crosstalk, ignore them

# Location for RRD database files and graphs (folder must be writable by overwatch process)
rrdFileStore = "./DB/"
rrdGraphStore = "./Graphs/"

# Display + animation
invertDisplay = False  # Is the display 'upside down'? generally the ribbon connection from the glass is at the bottom
passtime = 2           # time between display refresh cycles (seconds)
passes = 3             # number of refreshes of a screen before moving to next
slidespeed = 16        # number of rows to scroll on each animation step between screens

#
# End of user config
#

# Start by re-nicing so we dont block anything important
import os
os.nice(10)

# Some general functions we will use
import time
import datetime
import subprocess

# I2C Comms
from board import SCL, SDA
import busio

# I2C 128x64 OLED Display
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# BME280 I2C Tepmerature Pressure and Humidity sensor
import adafruit_bme280

# GPIO light control
import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread, current_thread

# RRD database
import rrdtool
from pathlib import Path

# Scheduler and Logging
import schedule
import logging
from logging.handlers import RotatingFileHandler

# Exit Handler
import atexit

# Let the console know we are starting
print("Starting OverWatch")

# Logging 
handler = RotatingFileHandler(logFile, maxBytes=1024*1024, backupCount=2)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S', handlers=[handler])
# Scheduler sometimes logs schedule actions to 'INFO' not 'DEBUG', spewing debug into the log, sigh..
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.WARN)

# Now we have logging, notify we are starting up
logging.info('')
logging.info("Starting " + serverName)

# Create the I2C interface object
i2c = busio.I2C(SCL, SDA)

# Create the I2C SSD1306 OLED object
# The first two parameters are the pixel width and pixel height.
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
# Immediately blank the display in case it is showing garbage
disp.fill(0)
disp.show()

# Create the I2C BME280 sensor object
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=bme280_address)

# GPIO mode and arrays for the pin database path and current status
if (len(pinMap) > 0):
    GPIO.setmode(GPIO.BCM)  # Set's GPIO pins to BCM GPIO numbering
pinState = []
pinDB = []

# Image canvas
margin = 20           # Space between the screens while transitioning
width  = disp.width
span   = width*2 + margin
height = disp.height

# Create image canvas (with mode '1' for 1-bit color)
image = Image.new("1", (span, height))

# Get drawing object so we can easily draw on canvas.
draw = ImageDraw.Draw(image)

# LiberationMono-Regular : nice font that looks clear on the small display
# This font is located in: /usr/share/fonts/truetype/liberation/ on Raspian.
# If you get an error that it is not present, install it with:
#   sudo apt install fonts-liberation
font = ImageFont.truetype('LiberationMono-Regular.ttf', 16)

# Unicode characters needed for display
degree_sign= u'\N{DEGREE SIGN}'

# Commands used to gather CPU data
cpuCmd = "cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.1f\", $1/1000}'"
topCmd = "top -bn1 | grep load | awk '{printf \"%.3f\", $(NF-2)}'"
memCmd = "free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2 }'"

# Initial values for the sensor readings
TMP = "undefined"
HUM = "undefined"
PRE = "undefined"
CPU = "undefined"
TOP = "undefined"
MEM = "undefined"

# Local functions

def clean():
    # Draw a black filled box to clear the canvas.
    draw.rectangle((0,0,span-1,height-1), outline=0, fill=0)

def show(xpos=0):
    # Put a specific area of the canvas onto display
    if invertDisplay:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)).transpose(Image.ROTATE_180))
    else:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)))
    disp.show()

def slideout(step=slidespeed):
    # Slide the display view across the canvas to animate between screens
    x = 0
    while x < width + margin:
        show(x)
        x = x + step
    show(width + margin)

def bmeScreen(xpos=0):
    draw.text((xpos,  5), 'Temp : ' + format(TMP, '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(HUM, '.1f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(PRE, '.0f') + 'mb',  font=font, fill=255)

def sysScreen(xpos=0):
    draw.text((xpos, 5), 'CPU  : ' + CPU + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Load : ' + TOP, font=font, fill=255)
    draw.text((xpos, 45), 'Mem  : ' + MEM + '%',  font=font, fill=255)

def getBmeData():
    global TMP, HUM, PRE
    # Gather BME280 sensor data.
    TMP = bme280.temperature
    HUM = bme280.relative_humidity
    PRE = bme280.pressure

def getSysData():
    global CPU, TOP, MEM
    # Shell commands to grab and parse system data
    CPU = subprocess.check_output(cpuCmd, shell=True).decode('utf-8')
    TOP = subprocess.check_output(topCmd, shell=True).decode('utf-8')
    MEM = subprocess.check_output(memCmd, shell=True).decode('utf-8')

def toggleButtonPin(action="toggle"):
    # Set the first pin to a specified state or read and toggle it..
    if (len(pinMap) > 0):
        if (action == 'toggle'):
            if (GPIO.input(pinMap[0][1]) == True):
                GPIO.output(pinMap[0][1],False)
                return pinMap[0][0] + 'Toggled : off'
            else:
                GPIO.output(pinMap[0][1],True)
                return pinMap[0][0] + 'Toggled : on'
        elif (action == 'on'):
            GPIO.output(pinMap[0][1],True)
            return pinMap[0][0] + 'Switched : on'
        elif (action == 'off'):
            GPIO.output(pinMap[0][1],False)
            return pinMap[0][0] + 'Switched : off'
        else:
            return 'I dont know how to "' + action + '" ' + pinMap[0][0] + '!'
    else:
        return 'Not supported, no output pin defined'

def buttonInterrupt(channel):
    # short delay, then re-read input to provide a minimum hold-down time
    # and suppress false triggers from other gpio operations
    time.sleep(0.1)
    if (GPIO.input(button_PIN) == True):
        logging.info('Button pressed')
        toggleButtonPin()
    elif (not suppressGlitches):
        logging.info('Button GLITCH')

def ServeHTTP():
    # Spawns a http.server.HTTPServer in a separate thread on the given port.
    handler = _BaseRequestHandler
    httpd = http.server.HTTPServer((host, port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well (left here to make obvious).
    httpd.allow_reuse_address = True
    threadlog("HTTP server will bind to port " + str(port) + " on host " + host)
    httpd.server_bind()
    address = "http://%s:%d" % (httpd.server_name, httpd.server_port)
    threadlog("Access via: " + address)
    httpd.server_activate()
    def serve_forever(httpd):
        with httpd:  # to make sure httpd.server_close is called
            threadlog("Http Server start")
            httpd.serve_forever()
            threadlog("Http Server closing down")
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.setDaemon(True)
    thread.start()
    return httpd, address

def threadlog(logline):
    # A wrapper function around logging.info() that prepends the current thread name
    logging.info("[" + current_thread().name + "] : " + logline)

class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def _give_head(self, scrolldown = False):
        self.wfile.write(bytes('<html>\n<head><meta charset="utf-8">\n', 'utf-8'))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">\n', 'utf-8'))
        self.wfile.write(bytes('<title>%s</title>\n' % serverName, 'utf-8'))
        self.wfile.write(bytes('<style>\n', 'utf-8'))
        self.wfile.write(bytes('body {display:flex; flex-direction: column; align-items: center;}\n', 'utf-8'))
        self.wfile.write(bytes('table {border-spacing: 0.2em;}\n', 'utf-8'))
        self.wfile.write(bytes('td {padding-left: 1em;}\n', 'utf-8'))
        self.wfile.write(bytes('</style>\n', 'utf-8'))
        if (scrolldown):
            self.wfile.write(bytes("<script>\n", 'utf-8'))
            self.wfile.write(bytes('function down() {\n', 'utf-8'))
            self.wfile.write(bytes('    window.scrollTo(0,document.body.scrollHeight);\n', 'utf-8'))
            self.wfile.write(bytes('}\n', 'utf-8'))
            self.wfile.write(bytes('window.onload = down;\n', 'utf-8'))
            self.wfile.write(bytes('</script>\n', 'utf-8'))
        self.wfile.write(bytes('</head>\n', 'utf-8'))
        self.wfile.write(bytes('<body>\n', 'utf-8'))

    def _give_foot(self,refresh = False):
            # DEBUG: self.wfile.write(bytes('<pre style="color:#888888">GET: ' + self.path + ' from: ' + self.client_address[0] + '</pre>\n', 'utf-8'))
            self.wfile.write(bytes('</body>\n', 'utf-8'))
            if (refresh):
                self.wfile.write(bytes("<script>\n", 'utf-8'))
                self.wfile.write(bytes('setTimeout(function(){location.replace(document.URL);}, 60000);\n', 'utf-8'))
                self.wfile.write(bytes('</script>\n', 'utf-8'))
            self.wfile.write(bytes('</html>\n', 'utf-8'))

    def _give_datetime(self):
        timestamp = datetime.datetime.now()
        self.wfile.write(bytes('<p style="color:#666666">' + timestamp.strftime("%H:%M:%S, %A, %d %B, %Y") + '</p>', 'utf-8'))

    def _give_env(self):
        # room sensors
        self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Room</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(TMP, '.1f') + '&deg;</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(HUM, '.1f') + '%</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(PRE, '.0f') + 'mb</td></tr>\n', 'utf-8'))

    def _give_sys(self):
        # Internal Sensors
        self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Server</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + CPU + '&deg;</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + TOP + '</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + MEM + '%</td></tr>\n', 'utf-8'))

    def _give_pins(self):
        # GPIO states
        if (len(pinMap) > 0):
            self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">GPIO</th></tr>\n', 'utf-8'))
            for i in range(len(pinMap)):
                if (pinState[i]):
                    self.wfile.write(bytes('<tr><td>' + pinMap[i][0] +'</td><td>on</td></tr>\n', 'utf-8'))
                else:
                    self.wfile.write(bytes('<tr><td>' + pinMap[i][0] +'</td><td>off</td></tr>\n', 'utf-8'))

    def _give_links(self):
        # Links to other pages
        self.wfile.write(bytes('<p style="text-align: center;">', 'utf-8'))
        self.wfile.write(bytes('<a href="./graph" style="color:#666666; font-weight: bold; text-decoration: none;">View Graphs</a><br>', 'utf-8'))
        self.wfile.write(bytes('<a href="?view=log&lines=' + str(logLines) + '" style="color:#666666; font-weight: bold; text-decoration: none;">View Log</a>', 'utf-8'))
        self.wfile.write(bytes('</p>\n', 'utf-8'))

    def _give_log(self,lines = 10):
        parsedLines = parse_qs(urlparse(self.path).query).get('lines', None)
        if (parsedLines):
            lines = parsedLines[0]
        # LogCmd is a shell one-liner used to extract the last {lines} of data from the logs
        # There is doubtless a more 'python' way to do this, but it is fast, cheap and works..
        logCmd = f"for a in `ls -tr {logFile}*`;do cat $a ; done | tail -{lines}"
        log = subprocess.check_output(logCmd, shell=True).decode('utf-8')
        self.wfile.write(bytes('<div><span style="font-size: 110%; font-weight: bold; text-decoration: none;">Recent log activity:</span><hr>', 'utf-8'))
        self.wfile.write(bytes('<pre>\n' + log + '<pre>\n', 'utf-8'))
        self.wfile.write(bytes(f'<p>Latest {lines} lines shown</p>', 'utf-8'))

    def do_GET(self):
        if (urlparse(self.path).path == '/graph'):
            parsed = parse_qs(urlparse(self.path).query).get('duration', None)
            if (not parsed):
                duration = "1d"
            else:
                duration = parsed[0]
            logging.info('Graph Generation (-' + duration + ' -> now) triggered by: ' + self.client_address[0])
            drawAllGraphs(duration)
            self._set_headers()
            self._give_head()
            self.wfile.write(bytes('<h4>Graphs Generated (-' + duration + ' -> now) </h4>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif ((urlparse(self.path).path == '/' + buttonPath) and (len(buttonPath) > 0)):
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if (not parsed):
                action = 'toggle'
            else:
                action = parsed[0]
            logging.info('Web button triggered by: ' + self.client_address[0] + ' with action: ' + action)
            state = toggleButtonPin(action)
            self._set_headers()
            self._give_head()
            self.wfile.write(bytes('<h2>' + state + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif(urlparse(self.path).path == '/'):
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if (not view):
                view = ["env", "sys", "gpio", "links"]
            self._set_headers()
            self._give_head()
            self.wfile.write(bytes('<h2>%s</h2>' % serverName, 'utf-8'))
            self._give_datetime()
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            if "env" in view: self._give_env()
            if "sys" in view: self._give_sys()
            if "gpio" in view: self._give_pins()
            self.wfile.write(bytes('</table>', 'utf-8'))
            if "links" in view: self._give_links()
            if "log" in view: self._give_log()
            self.wfile.write(bytes('<hr></div>', 'utf-8'))
            self._give_foot(refresh=True)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at ".../" and ".../graph"')

    def do_HEAD(self):
        self._set_headers()

def updateData():
    # Get sensor data
    getBmeData()
    getSysData()
    # Check if any pins have changed state, and log
    for i in range(len(pinMap)):
        thisPinState =  GPIO.input(pinMap[i][1])
        if (thisPinState != pinState[i]):
            pinState[i] = thisPinState
            if (thisPinState):
                logging.info(pinMap[i][0] + ': on')
            else:
                logging.info(pinMap[i][0] + ': off')

def updateDB():
    updateCmd = "N:" + format(TMP, '.3f') + ":" + format(HUM, '.2f') + ":" + format(PRE, '.2f')
    rrdtool.update(str(envDB), updateCmd)
    updateCmd = "N:" + CPU + ":" + TOP + ":" + MEM
    rrdtool.update(str(sysDB), updateCmd)
    for i in range(len(pinDB)):
        updateCmd = "N:" + str(pinState[i])
        rrdtool.update(str(pinDB[i]), updateCmd)

def logSensors():
    logging.info('Temp: ' + format(TMP, '.1f') + degree_sign + ', Humi: ' + format(HUM, '.0f') + '%, Pres: ' + format(PRE, '.0f') + 'mb, CPU: ' + CPU + degree_sign + ', Load: ' + TOP + ', Mem: ' + MEM + '%')

def drawAllGraphs(period="1d"):
    allgraphs = ["env-temp","env-humi","env-pres","sys-temp","sys-load","sys-mem"]
    for p in pinMap:
        allgraphs.append("pin-" + p[0])
    for g in allgraphs:
        drawGraph(period,g)

def drawGraph(period,graph):
    # RRD graph generation
    print('Graph generation: graph ="' + graph + '", period="' + period + '"')
    graphWide = 1200
    graphHigh = 600
    lineW = 'LINE2:'
    lineC = '#FF00FF'
    start = 'end-' + period
    if (graph == "env-temp"):
        rrdtool.graph(rrdGraphStore + "env-temp-" + period + ".png",
                      "--vertical-label", "Room Temperature",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "60",
                      "--lower-limit", "10",
                      "--left-axis-format", "%3.1lf\u00B0C",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:envt=DB/env.rrd:env-temp:AVERAGE", lineW + 'envt' + lineC)
    elif (graph == "env-humi"):
        rrdtool.graph(rrdGraphStore + "env-humi-" + period + ".png",
                      "--vertical-label", "Room Humidity",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "100",
                      "--lower-limit", "0",
                      "--left-axis-format", "%3.0lf%%",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:envh=DB/env.rrd:env-humi:AVERAGE", lineW + 'envh' + lineC)
    elif (graph == "env-pres"):
        rrdtool.graph(rrdGraphStore + "env-pres-" + period + ".png",
                      "--vertical-label", "Room Pressure",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "1040",
                      "--lower-limit", "970",
                      "--units-exponent", "0",
                      "--left-axis-format", "%4.0lfmb",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:envp=DB/env.rrd:env-pres:AVERAGE", lineW + 'envp' + lineC)
    elif (graph == "sys-temp"):
        rrdtool.graph(rrdGraphStore + "sys-temp-" + period + ".png",
                      "--vertical-label", "CPU Temperature",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "90",
                      "--lower-limit", "30",
                      "--left-axis-format", "%3.1lf\u00B0C",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:syst=DB/sys.rrd:sys-temp:AVERAGE", lineW + 'syst' + lineC)
    elif (graph == "sys-load"):
        rrdtool.graph(rrdGraphStore + "sys-load-" + period + ".png",
                      "--vertical-label", "CPU Load Average",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "5",
                      "--lower-limit", "0",
                      "--units-exponent", "0",
                      "--left-axis-format", "%2.3lf",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:sysl=DB/sys.rrd:sys-load:AVERAGE", lineW + 'sysl' + lineC)
    elif (graph == "sys-mem"):
        rrdtool.graph(rrdGraphStore + "sys-mem-" + period + ".png",
                      "--vertical-label", "CPU Memory Used",
                      "--width", str(graphWide),
                      "--height", str(graphHigh),
                      "--full-size-mode",
                      "--start", start,
                      "--end", "now",
                      "--upper-limit", "100",
                      "--lower-limit", "0",
                      "--left-axis-format", "%3.0lf%%",
                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                      "DEF:sysm=DB/sys.rrd:sys-mem:AVERAGE", lineW + 'sysm' + lineC)
    else:
        for i in range(len(pinMap)):
            if (graph == "pin-" + pinMap[i][0]):
                rrdtool.graph(rrdGraphStore + "pin-" + pinMap[i][0] + "-" + period + ".png",
                              "--vertical-label", pinMap[i][0] + " Pin State",
                              "--width", str(graphWide),
                              "--height", str(graphHigh/3),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "1.1",
                              "--lower-limit", "-0.1",
                              "--left-axis-format", "%3.1lf",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:pinm=" + str(pinDB[i]) + ":status:AVERAGE", lineW + 'pinm' + lineC)

def scheduleRunDelay(seconds):
    # Approximate delay while checking for pending scheduled jobs every second
    schedule.run_pending()
    for t in range(seconds):
        time.sleep(1)
        schedule.run_pending()

def goodBye():
    logging.info('Exiting')

# The fun starts here:
if __name__ == "__main__":
    # Web Server
    ServeHTTP()

# Main RRDtool databases
    envDB = Path(rrdFileStore + "env.rrd")
    if not envDB.is_file():
        print("Generating " + str(envDB))
        rrdtool.create(
            str(envDB),
            "--start", "now",
            "--step", "60",
            "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
            "RRA:AVERAGE:0.5:60:17568",   # two years per hour
            "DS:env-temp:GAUGE:60:U:U",
            "DS:env-humi:GAUGE:60:U:U",
            "DS:env-pres:GAUGE:60:U:U")
    else:
        print("Using existing: " + str(envDB))

    sysDB = Path(rrdFileStore + "sys.rrd")
    if not sysDB.is_file():
        print("Generating " + str(sysDB))
        rrdtool.create(
            str(sysDB),
            "--start", "now",
            "--step", "60",
            "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
            "RRA:AVERAGE:0.5:60:17568",   # two years per hour
            "DS:sys-temp:GAUGE:60:U:U",
            "DS:sys-load:GAUGE:60:U:U",
            "DS:sys-mem:GAUGE:60:U:U")
    else:
        print("Using existing: " + str(sysDB))

    # Add RRD database for each GPIO line
    for i in range(len(pinMap)):
        pinDB.append(Path(rrdFileStore + pinMap[i][0] + ".rrd"))
        if not pinDB[i].is_file():
            print("Generating " + str(pinDB[i]))
            rrdtool.create(
                str(pinDB[i]),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:17568",   # two years per hour
                "DS:status:GAUGE:60:0:1")
        else:
            print("Using existing: " + str(pinDB[i]))

    # Set up the button pin interrupt (if defined, otherwise button is disabled)
    if (button_PIN > 0):
        GPIO.setup(button_PIN, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)
        logging.info('Button enabled')

    # Initial data readings
    getBmeData()
    getSysData()
    # Set all gpio pins to 'output' and record their initial status
    #   We need to set them as outputs in this scripts context in order to monitor their state.
    #   So long as we do not try to write to these pins this will not affect their output,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    for i in range(len(pinMap)):
        GPIO.setup(pinMap[i][1], GPIO.OUT)
        pinState.append(GPIO.input(pinMap[i][1]))
        if (pinState[i]):
            logging.info(pinMap[i][0] + ": on")
        else:
            logging.info(pinMap[i][0] + ": off")

    # Exit handler
    atexit.register(goodBye)

    # We got this far... time to start the show
    logging.info("Init complete, starting schedule and entering main loop")

    # Schedule sensor readings, database updates and logging events
    schedule.every(sensorInterval).seconds.do(updateData)
    schedule.every(20).seconds.do(updateDB)
    if (logInterval > 0):
        schedule.every(logInterval).seconds.do(logSensors)

    schedule.run_all() # do an initial log and database update

    # Main loop now runs forever
    while True:
        # Screen 1
        for i in range(passes):
            clean()
            bmeScreen()
            show()
            scheduleRunDelay(passtime)

        # Update and transition to screen 2
        bmeScreen()
        sysScreen(width+margin)
        slideout()
        scheduleRunDelay(passtime)

        # Screen 2
        for i in range(passes):
            clean()
            sysScreen()
            show()
            scheduleRunDelay(passtime)

        # Update and transition back to screen 1
        sysScreen()
        bmeScreen(width+margin)
        slideout()
        scheduleRunDelay(passtime)
