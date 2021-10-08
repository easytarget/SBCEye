#!/usr/bin/python

# Pi Overwatch:
# Animate the SSD1306 display attached to my OctoPrint server with bme280 and system data
# Show, log and graph the environmental, system and gpio data via a web interface
# Give me a on/off button + url to control the bench lights via a GPIO pin

# Default settings are in the file 'settings_default.py'
# Copy this to 'settings.py' and edit as appropriate
try:
    print("Loading settings from user settings file")
    from settings import settings as s
except (ModuleNotFoundError):
    print("No user settings found, loading from default settings file")
    from default_settings import settings as s

# I2C BME280 Sensor and SSD1306 Display:
#
# Note: the sensor and display are optional, if not found their functionality will be disabled and this will be logged at startup.
#
# Make sure I2C is enabled in 'boot/config.txt' (reboot after editing that file)
# Uncomment: "dtparam=i2c_arm=on", which is the same as you get if enabling I2C via the 'Interface Options' in `sudo raspi-config`
# I prefer 'dtparam=i2c_arm=on,i2c_arm_baudrate=400000', to draw the display faster, but is more prone to errors from long wires etc.. ymmv.

# To list all I2C addresses visible on the system run: `i2cdetect -y 1` (`sudo apt install i2c-tools`)
# bme280 I2C address should be 0x76 or 0x77 (this is selectable via a jumper) and we will search for it there
# The SSD1306 I2C address should be automagically found; the driver will bind to the first matching display

# Start by re-nicing so we dont block anything important
import os
os.nice(10)

# Some general functions we will use
import time
import datetime
import subprocess
import tempfile

# System monitoring tools
import psutil

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
handler = RotatingFileHandler(s.logFile, maxBytes=1024*1024, backupCount=2)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S', handlers=[handler])
# Older scheduler versions sometimes log actions to 'INFO' not 'DEBUG', spewing debug into the log, sigh..
schedule_logger = logging.getLogger('schedule')  # Oi! Schedule!
schedule_logger.setLevel(level=logging.WARN)     # Stop it.

# Now we have logging, notify we are starting up
logging.info('')
logging.info("Starting " + s.serverName)

try: 
    # Create the I2C interface object
    i2c = busio.I2C(SCL, SDA)
except Exception as e: 
    print(e)
    print("No I2C bus, screen and sensor functions will be disabled")

try:
    # Create the I2C SSD1306 OLED object
    # The first two parameters are the pixel width and pixel height.
    disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
    haveScreen = True
    disp.contrast(s.displayContrast)
    disp.invert(s.displayInvert)
    disp.fill(0)  # And blank as fast as possible in case it is showing garbage..
    disp.show()
    print("We have a Screen")
except:
    haveScreen = False
    print("We do not have a Screen")

try:
    # Create the I2C BME280 sensor object
    bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
    print("BME280 sensor found with address 0x76")
    haveSensor = True
except:
    try:
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
        print("BME280 sensor found with address 0x77")
        haveSensor = True
    except:
        print("No BME280 sensor found on addresses 0x76 or 0x77")
        haveSensor = False

# GPIO mode and arrays for the pin database path and current status
if (len(s.pinMap) > 0):
    GPIO.setmode(GPIO.BCM)  # Set's GPIO pins to BCM GPIO numbering
pinState = []

# RRD database file locations
envDB = Path(s.rrdFileStore + "env.rrd")
sysDB = Path(s.rrdFileStore + "sys.rrd")
pinDB = []
for i in range(len(s.pinMap)):
    pinDB.append(Path(s.rrdFileStore + s.pinMap[i][0] + ".rrd"))

if haveScreen:
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
else:
    # Ensure saver never triggers
    s.saverMode = "off"

# Current screensaver state
saverActive= False

# Unicode characters needed for display and logging
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
    if s.rotateDisplay:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)).transpose(Image.ROTATE_180))
    else:
        disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)))
    disp.show()

def slideout(step=s.slidespeed):
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
    if (len(s.pinMap) > 0):
        if (action == 'toggle'):
            if (GPIO.input(s.pinMap[0][1]) == True):
                GPIO.output(s.pinMap[0][1],False)
                return s.pinMap[0][0] + ' Toggled: off'
            else:
                GPIO.output(s.pinMap[0][1],True)
                return s.pinMap[0][0] + ' Toggled: on'
        elif (action == 'on'):
            GPIO.output(s.pinMap[0][1],True)
            return s.pinMap[0][0] + ' Switched: on'
        elif (action == 'off'):
            GPIO.output(s.pinMap[0][1],False)
            return s.pinMap[0][0] + ' Switched: off'
        else:
            return 'I dont know how to "' + action + '" ' + s.pinMap[0][0] + '!'
    else:
        return 'Not supported, no output pin defined'

def buttonInterrupt(channel):
    # short delay, then re-read input to provide a minimum hold-down time
    # and suppress false triggers from other gpio operations
    time.sleep(0.1)
    if (GPIO.input(s.button_PIN) == True):
        logging.info('Button pressed')
        toggleButtonPin()
    elif (not s.suppressGlitches):
        logging.info('Button GLITCH')

def ServeHTTP():
    # Spawns a http.server.HTTPServer in a separate thread on the given port.
    handler = _BaseRequestHandler
    httpd = http.server.HTTPServer((s.host, s.port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well (left here to make obvious).
    httpd.allow_reuse_address = True
    threadlog("HTTP server will bind to port " + str(s.port) + " on host " + s.host)
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

    def _set_png_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "image/png")
        self.send_header("Cache-Control", "max-age=60")
        self.end_headers()

    def _give_head(self, titleExtra=""):
        title = s.serverName
        if (len(titleExtra) > 0):
            title= s.serverName +" :: " + titleExtra
        self.wfile.write(bytes('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n', 'utf-8'))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">\n', 'utf-8'))
        self.wfile.write(bytes('<title>%s</title>\n' % title, 'utf-8'))
        self.wfile.write(bytes('<style>\n', 'utf-8'))
        self.wfile.write(bytes('body {display:flex; flex-direction: column; align-items: center;}\n', 'utf-8'))
        self.wfile.write(bytes('a {color:#666666; text-decoration: none;}\n', 'utf-8'))
        self.wfile.write(bytes('img {width:auto; max-width:100%;}\n', 'utf-8'))
        self.wfile.write(bytes('table {border-spacing: 0.2em; width:auto; max-width:100%;}\n', 'utf-8'))
        self.wfile.write(bytes('th {font-size: 110%; text-align: left;}\n', 'utf-8'))
        self.wfile.write(bytes('td {padding-left: 1em;}\n', 'utf-8'))
        self.wfile.write(bytes('</style>\n', 'utf-8'))
        self.wfile.write(bytes('</head>\n', 'utf-8'))
        self.wfile.write(bytes('<body>\n', 'utf-8'))

    def _give_foot(self,scroll = False, refresh = 0):
            # DEBUG: self.wfile.write(bytes('<pre style="color:#888888">GET: ' + self.path + ' from: ' + self.client_address[0] + '</pre>\n', 'utf-8'))
            self.wfile.write(bytes('</body>\n', 'utf-8'))
            self.wfile.write(bytes("<script>\n", 'utf-8'))
            if (scroll):
                self.wfile.write(bytes('function down() {\n', 'utf-8'))
                self.wfile.write(bytes('    window.scrollTo(0,document.body.scrollHeight);\n', 'utf-8'))
                self.wfile.write(bytes('    console.log("SCROLL" + document.body.scrollHeight);\n', 'utf-8'))
                self.wfile.write(bytes('}\n', 'utf-8'))
                self.wfile.write(bytes('window.onload = down;\n', 'utf-8'))
            if (refresh > 0):
                self.wfile.write(bytes('setTimeout(function(){location.replace(document.URL);}, ' + str(refresh*1000) + ');\n', 'utf-8'))
            self.wfile.write(bytes('</script>\n', 'utf-8'))
            self.wfile.write(bytes('</html>\n', 'utf-8'))

    def _give_datetime(self):
        timestamp = datetime.datetime.now()
        self.wfile.write(bytes('<div style="color:#666666; font-size: 90%">' + timestamp.strftime("%H:%M:%S, %A, %d %B, %Y") + '</div>\n', 'utf-8'))

    def _give_env(self):
        if haveSensor:
            # room sensors
            self.wfile.write(bytes('<tr><th>Room</th></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(TMP, '.1f') + '&deg;</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(HUM, '.1f') + '%</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(PRE, '.0f') + 'mb</td></tr>\n', 'utf-8'))

    def _give_sys(self):
        # Internal Sensors
        self.wfile.write(bytes('<tr><th>Server</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + CPU + '&deg;</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + TOP + '</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + MEM + '%</td></tr>\n', 'utf-8'))

    def _give_pins(self):
        # GPIO states
        if (len(s.pinMap) > 0):
            self.wfile.write(bytes('<tr><th>GPIO</th></tr>\n', 'utf-8'))
            for p in range(len(s.pinMap)):
                if (pinState[p]):
                    self.wfile.write(bytes('<tr><td>' + s.pinMap[p][0] +'</td><td>on</td></tr>\n', 'utf-8'))
                else:
                    self.wfile.write(bytes('<tr><td>' + s.pinMap[p][0] +'</td><td>off</td></tr>\n', 'utf-8'))

    def _give_links(self):
        # Links to other pages
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><th>Graph:</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>\n', 'utf-8'))
        for g in s.graphDefaults:
            self.wfile.write(bytes('&nbsp;<a href="./graphs?duration=' + g + '">' + g + '</a>&nbsp;\n', 'utf-8'))
        self.wfile.write(bytes('</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('</table>\n', 'utf-8'))
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes('<tr>\n', 'utf-8'))
        self.wfile.write(bytes('<td><a href="?view=deco&view=env&view=sys&view=gpio&view=links&view=log">Inline Log</a></td>\n', 'utf-8'))
        self.wfile.write(bytes('<td><a href="?view=deco&view=log&lines=' + str(s.logLines) + '">Main Log</a></td>\n', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))
        self.wfile.write(bytes('</table>\n', 'utf-8'))

    def _give_log(self,lines = 10):
        parsedLines = parse_qs(urlparse(self.path).query).get('lines', None)
        if (parsedLines):
            lines = parsedLines[0]
        # LogCmd is a shell one-liner used to extract the last {lines} of data from the logs
        # There is doubtless a more 'python' way to do this, but it is fast, cheap and works..
        logCmd = f"for a in `ls -tr {s.logFile}*`;do cat $a ; done | tail -{lines}"
        log = subprocess.check_output(logCmd, shell=True).decode('utf-8')
        self.wfile.write(bytes('<div style="overflow-x: auto; width: 100%;">\n', 'utf-8'))
        self.wfile.write(bytes('<span style="font-size: 110%; font-weight: bold;">Recent log activity:</span>\n', 'utf-8'))
        self.wfile.write(bytes('<hr><pre>\n' + log + '</pre><hr>\n', 'utf-8'))
        self.wfile.write(bytes(f'Latest {lines} lines shown\n', 'utf-8'))
        self.wfile.write(bytes('</div>\n', 'utf-8'))

    def _give_graphs(self,d):
        if haveSensor:
            allgraphs = [["env-temp","Temperature"],
                         ["env-humi","Humidity"],
                         ["env-pres","Pressure"],
                         ["sys-temp","CPU Temperature"],
                         ["sys-load","CPU Load Average"],
                         ["sys-mem","System Memory Use"]]
        else:
            allgraphs = [["sys-temp","CPU Temperature"],
                         ["sys-load","CPU Load Average"],
                         ["sys-mem","System Memory Use"]]
        for p in s.pinMap:
            allgraphs.append(["pin-" + p[0],p[0] + " GPIO"])
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><th>Graphs: -' + d + ' -> now</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>\n', 'utf-8'))
        for [g,t] in allgraphs:
            self.wfile.write(bytes('<tr><td><a href="graph?graph=' + g + '&duration=' + d + '">', 'utf-8'))
            self.wfile.write(bytes('<img title="' + t + '" src="graph?graph=' + g + '&duration=' + d + '">', 'utf-8'))
            self.wfile.write(bytes('</a></td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('</table>\n', 'utf-8'))

    def do_GET(self):
        if (urlparse(self.path).path == '/graph'):
            parsedGraph = parse_qs(urlparse(self.path).query).get('graph', None)
            parsedDuration = parse_qs(urlparse(self.path).query).get('duration', None)
            if (not parsedGraph):
                body = ""
            elif (not parsedDuration):
                body = ""
            else:
                graph = parsedGraph[0]
                duration = parsedDuration[0]
                # logging.info('Graph Generation requested for: ' + graph + '(-' + duration + ' -> now) triggered by: ' + self.client_address[0])
                body = drawGraph(duration,graph)
            if (len(body) == 0):
                self.send_error(404, 'Image Unavailable', 'Check your parameters and try again')
                return
            self._set_png_headers()
            self.wfile.write(body)
        elif (urlparse(self.path).path == '/graphs'):
            parsed = parse_qs(urlparse(self.path).query).get('duration', None)
            if (not parsed):
                duration = "1d"
            else:
                duration = parsed[0]
            # logging.info('Graph Page (-' + duration + ' -> now) requested by: ' + self.client_address[0])
            self._set_headers()
            self._give_head(s.serverName + ":: graphs -" + duration)
            self.wfile.write(bytes('<h2>%s</h2>' % s.serverName, 'utf-8')) 
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            self._give_graphs(duration)
            self.wfile.write(bytes('</table>', 'utf-8'))
            self._give_datetime()
            self._give_foot(refresh=300)
        elif ((urlparse(self.path).path == '/c')):
            parsed = parse_qs(urlparse(self.path).query).get('c', None)
            if (not parsed):
                c = 0xff 
            else:
                c = int(parsed[0])
            logging.info('Contrast: ' + self.client_address[0] + ' with action: ' + str(c))
            disp.contrast(c)
            self._set_headers()
            self._give_head(s.serverName + ":: c=" + str(c))
            self.wfile.write(bytes('<h2>' + str(c) + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif ((urlparse(self.path).path == '/i')):
            parsed = parse_qs(urlparse(self.path).query).get('i', None)
            if (not parsed):
                i = False 
            else:
                i = True
            logging.info('Invert: ' + self.client_address[0] + ' with action: ' + str(i))
            disp.invert(i)
            self._set_headers()
            self._give_head(s.serverName + ":: i=" + str(i))
            self.wfile.write(bytes('<h2>' + str(i) + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif ((urlparse(self.path).path == '/' + s.buttonPath) and (len(s.buttonPath) > 0)):
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if (not parsed):
                action = 'toggle'
            else:
                action = parsed[0]
            logging.info('Web button triggered by: ' + self.client_address[0] + ' with action: ' + action)
            state = toggleButtonPin(action)
            self._set_headers()
            self._give_head(s.serverName + ":: " + s.pinMap[0][0])
            self.wfile.write(bytes('<h2>' + state + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif(urlparse(self.path).path == '/'):
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if (not view):
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            self._give_head()
            if "deco" in view: self.wfile.write(bytes('<h2>%s</h2>\n' % s.serverName, 'utf-8'))
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            if "env" in view: self._give_env()
            if "sys" in view: self._give_sys()
            if "gpio" in view: self._give_pins()
            self.wfile.write(bytes('</table>\n', 'utf-8'))
            if "links" in view: self._give_links()
            if "log" in view:
                self._give_log()
                if "deco" in view: self._give_datetime()
                self._give_foot(refresh = 60, scroll = True) 
            else:
                if "deco" in view: 
                    self.wfile.write(bytes('<br>', 'utf-8'))
                    self._give_datetime()
                self._give_foot(refresh = 60)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at ".../" and ".../graph"')

    def do_HEAD(self):
        self._set_headers()

def setSaver(on):
    global saverActive
    if (on):
        print("Saver Enabled")
        saverActive = True
        if (s.saverMode == 'invert'):
            disp.invert(not s.displayInvert)
        elif (s.saverMode == 'blank'):
            disp.poweroff()
    else:
        print("Saver Disabled")
        saverActive = False
        if (s.saverMode == 'invert'):
            disp.invert(s.displayInvert)
        elif (s.saverMode == 'blank'):
            disp.poweron()

def updateData():
    # Runs every few seconds to get current environmental and system data
    if haveSensor:
        getBmeData()
    getSysData()

    #print(psutil.virtual_memory().percent, psutil.getloadavg()[0], psutil.sensors_temperatures())
    #temps = psutil.sensors_temperatures()
    #for name, entries in temps.items():
    #    print(name)
    #    print(entries[0])
    #print(psutil.sensors_temperatures().cpu_thermal)

    # Check if any pins have changed state, and log
    for i in range(len(s.pinMap)):
        thisPinState =  GPIO.input(s.pinMap[i][1])
        if (thisPinState != pinState[i]):
            pinState[i] = thisPinState
            if (thisPinState):
                logging.info(s.pinMap[i][0] + ': on')
            else:
                logging.info(s.pinMap[i][0] + ': off')

def updateDB():
    # Runs 3x per minute, updates RRD database and processes screensaver
    if haveSensor:
        updateCmd = "N:" + format(TMP, '.3f') + ":" + format(HUM, '.2f') + ":" + format(PRE, '.2f')
        rrdtool.update(str(envDB), updateCmd)
    updateCmd = "N:" + CPU + ":" + TOP + ":" + MEM
    rrdtool.update(str(sysDB), updateCmd)
    for i in range(len(pinDB)):
        updateCmd = "N:" + str(pinState[i])
        rrdtool.update(str(pinDB[i]), updateCmd)
    if (s.saverMode != 'off'):
        hour = time.localtime()[4]
        if ((hour == s.saverOn) and not saverActive):
            setSaver(True)
        elif ((hour == s.saverOff) and saverActive):
            setSaver(False)

def logSensors():
    # Runs on a user defined schedule to dump a line of sensor data in the log
    if haveSensor:
        logging.info('Temp: ' + format(TMP, '.1f') + degree_sign + ', Humi: ' + format(HUM, '.0f') + '%, Pres: ' + format(PRE, '.0f') + 'mb, CPU: ' + CPU + degree_sign + ', Load: ' + TOP + ', Mem: ' + MEM + '%')
    else:
        logging.info('CPU: ' + CPU + degree_sign + ', Load: ' + TOP + ', Mem: ' + MEM + '%')

def drawGraph(period,graph):
    # RRD graph generation
    # Returns the generated file for sending in the http response
    tempf = tempfile.NamedTemporaryFile(mode='rb', dir='/tmp', prefix='overwatch_graph')
    start = 'end-' + period
    if (graph == "env-temp"):
        try:
            rrdtool.graph(tempf.name, "--title", "Environment Temperature: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "45",
                          "--lower-limit", "10",
                          "--left-axis-format", "%3.1lf\u00B0C",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:envt=" + str(envDB) + ":env-temp:AVERAGE", s.areaW + 'envt' + s.areaC, s.lineW + 'envt' + s.lineC)
        except Exception:
            pass
    elif (graph == "env-humi"):
        try:
            rrdtool.graph(tempf.name, "--title", "Environment Humidity: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "100",
                          "--lower-limit", "0",
                          "--left-axis-format", "%3.0lf%%",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:envh=" + str(envDB) + ":env-humi:AVERAGE", s.areaW + 'envh' + s.areaC, s.lineW + 'envh' + s.lineC)
        except Exception:
            pass
    elif (graph == "env-pres"):
        try:
            rrdtool.graph(tempf.name, "--title", "Environment Pressure: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "1040",
                          "--lower-limit", "970",
                          "--units-exponent", "0",
                          "--left-axis-format", "%4.0lfmb",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:envp=" + str(envDB) + ":env-pres:AVERAGE", s.areaW + 'envp' + s.areaC, s.lineW + 'envp' + s.lineC)
        except Exception:
            pass
    elif (graph == "sys-temp"):
        try:
            rrdtool.graph(tempf.name, "--title", "CPU Temperature: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "90",
                          "--lower-limit", "30",
                          "--left-axis-format", "%3.1lf\u00B0C",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:syst=" + str(sysDB) + ":sys-temp:AVERAGE", s.areaW + 'syst' + s.areaC, s.lineW + 'syst' + s.lineC)
        except Exception:
            pass
    elif (graph == "sys-load"):
        try:
            rrdtool.graph(tempf.name, "--title", "CPU Load Average: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "3",
                          "--lower-limit", "0",
                          "--units-exponent", "0",
                          "--left-axis-format", "%2.3lf",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:sysl=" + str(sysDB) + ":sys-load:AVERAGE", s.areaW + 'sysl' + s.areaC, s.lineW + 'sysl' + s.lineC)
        except Exception:
            pass
    elif (graph == "sys-mem"):
        try:
            rrdtool.graph(tempf.name, "--title", "System Memory Use: last " + period,
                          "--width", str(s.graphWide),
                          "--height", str(s.graphHigh),
                          "--full-size-mode",
                          "--start", start,
                          "--end", "now",
                          "--upper-limit", "100",
                          "--lower-limit", "0",
                          "--left-axis-format", "%3.0lf%%",
                          "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                          "DEF:sysm=" + str(sysDB) + ":sys-mem:AVERAGE", s.areaW + 'sysm' + s.areaC, s.lineW + 'sysm' + s.lineC)
        except Exception:
            pass
    else:
        for i in range(len(s.pinMap)):
            if (graph == "pin-" + s.pinMap[i][0]):
                try:
                    rrdtool.graph(tempf.name, "--title", s.pinMap[i][0] + " Pin State: last " + period,
                                  "--width", str(s.graphWide),
                                  "--height", str(s.graphHigh/2),
                                  "--full-size-mode",
                                  "--start", start,
                                  "--end", "now",
                                  "--upper-limit", "1.1",
                                  "--lower-limit", "-0.1",
                                  "--left-axis-format", "%3.1lf",
                                  "--watermark", s.serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                                  "DEF:pinv=" + str(pinDB[i]) + ":status:AVERAGE", s.areaW + 'pinv' + s.areaC, s.lineW + 'pinv' + s.lineC)
                except Exception:
                    pass
    response = tempf.read()
    if (len(response) == 0):
        print("Error: png file generation failed for : " + graph + " : " + period)
    tempf.close()
    return response

def scheduleRunDelay(seconds=60):
    # Approximate delay while checking for pending scheduled jobs every second
    schedule.run_pending()
    for t in range(seconds):
        time.sleep(1)
        schedule.run_pending()

def goodBye():
    logging.info('Exiting')

# The fun starts here:
if __name__ == "__main__":

    if (haveScreen):
        # Splash!
        draw.text((10, 10), 'Over-',  font=font, fill=255)
        draw.text((28, 28), 'Watch',  font=font, fill=255)
        show()

    # Do an initial, early, data reading to settle sensors etc
    if haveSensor: getBmeData()
    getSysData()

    # Web Server
    ServeHTTP()

# Main RRDtool databases
    if haveSensor:
        if not envDB.is_file():
            print("Generating " + str(envDB))
            rrdtool.create(
                str(envDB),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                "DS:env-temp:GAUGE:60:U:U",
                "DS:env-humi:GAUGE:60:U:U",
                "DS:env-pres:GAUGE:60:U:U")
        else:
            print("Using existing: " + str(envDB))

    if not sysDB.is_file():
        print("Generating " + str(sysDB))
        rrdtool.create(
            str(sysDB),
            "--start", "now",
            "--step", "60",
            "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
            "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
            "DS:sys-temp:GAUGE:60:U:U",
            "DS:sys-load:GAUGE:60:U:U",
            "DS:sys-mem:GAUGE:60:U:U")
    else:
        print("Using existing: " + str(sysDB))

    # Add RRD database for each GPIO line
    for i in range(len(s.pinMap)):
        if not pinDB[i].is_file():
            print("Generating " + str(pinDB[i]))
            rrdtool.create(
                str(pinDB[i]),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                "DS:status:GAUGE:60:0:1")
        else:
            print("Using existing: " + str(pinDB[i]))

    # Set up the button pin interrupt (if defined, otherwise button is disabled)
    if (s.button_PIN > 0):
        GPIO.setup(s.button_PIN, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(s.button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)
        logging.info('Button enabled')

    # Set all gpio pins to 'output' and record their initial status
    #   We need to set them as outputs in this scripts context in order to monitor their state.
    #   So long as we do not try to write to these pins this will not affect their output,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    for i in range(len(s.pinMap)):
        GPIO.setup(s.pinMap[i][1], GPIO.OUT)
        pinState.append(GPIO.input(s.pinMap[i][1]))
        if (pinState[i]):
            logging.info(s.pinMap[i][0] + ": on")
        else:
            logging.info(s.pinMap[i][0] + ": off")

    # Exit handler
    atexit.register(goodBye)

    # Warn if we are missing sensor or screen
    if not haveScreen: logging.warning("No screen detected, screen features disabled")
    if not haveSensor: logging.warning("No environmental sensor detected, reporting and logging disabled")
    if (len(s.pinMap) == 0): logging.warning("No GPIO map provided, GPIO reporting and logging disabled")

    # We got this far... time to start the show
    logging.info("Init complete, starting schedule and entering main loop")

    # Schedule sensor readings, database updates and logging events
    schedule.every(s.sensorInterval).seconds.do(updateData)
    schedule.every(20).seconds.do(updateDB)
    if (s.logInterval > 0):
        schedule.every(s.logInterval).seconds.do(logSensors)

    schedule.run_all() # do an initial log and database update

    # Main loop now runs forever
    while True:
        if haveScreen:
            if haveSensor:
                # Environment Screen
                for i in range(s.passes):
                    clean()
                    bmeScreen()
                    show()
                    scheduleRunDelay(s.passtime)
                # Update and transition to system screen
                bmeScreen()
                sysScreen(width+margin)
                slideout()
                scheduleRunDelay(s.passtime)
                # System screen
                for i in range(s.passes):
                    clean()
                    sysScreen()
                    show()
                    scheduleRunDelay(s.passtime)
                # Update and transition back to environment screen
                sysScreen()
                bmeScreen(width+margin)
                slideout()
                scheduleRunDelay(s.passtime)
            else:
                # Just loop refreshing the system screen
                for i in range(s.passes):
                    clean()
                    sysScreen()
                    show()
                    scheduleRunDelay(s.passtime)
        else:
            # No screen, so just run schedule jobs in a loop
            scheduleRunDelay()
