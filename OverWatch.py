#!/usr/bin/python

# Pi Overwatch:
# Animate the SSD1306 display attached to my OctoPrint server with bme280 and system data
# Show, log and graph the environmental, system and gpio data via a web interface
# Give me a on/off button + url to control the bench lights via a GPIO pin

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

# Default settings are in the file 'settings_default.py'
# Copy this to 'settings.py' and edit as appropriate

try:
    print("Loading settings from user settings file")
    from settings import settings as s
except (ModuleNotFoundError):
    print("No user settings found, loading from default settings file")
    from default_settings import settings as s

# Local classes
from saver import saver
from rrd import rrd

# Some general functions we will use
import os
import time
import datetime
import subprocess

# System monitoring tools
import psutil

# I2C Comms
try:
    from board import SCL, SDA
    import busio
except:
    print("I2C bus requirements not met")

# I2C 128x64 OLED Display
from PIL import Image, ImageDraw, ImageFont
try:
    import adafruit_ssd1306
except:
    print("ssd1306 display requirements not met")

# BME280 I2C Tepmerature Pressure and Humidity sensor
try:
    import adafruit_bme280
except:
    print("BME280 ienvironment sensor requirements not met")

# GPIO light control
import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread, current_thread

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
        print("We do not have an environmental sensor")
        haveSensor = False

# GPIO mode and arrays for the pin database path and current status
if (len(s.pinMap) > 0):
    GPIO.setmode(GPIO.BCM)  # Set's GPIO pins to BCM GPIO numbering
pinState = []

# Display setup
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

    # Start saver
    screensaver = saver(disp, s.saverMode, s.saverOn, s.saverOff, s.displayInvert)
else:
    # Ensure saver never triggers
    s.saverMode = "off"

# Unicode characters needed for display and logging
degree_sign= u'\N{DEGREE SIGN}'

# RRD init
rrd = rrd(s.rrdFileStore, haveSensor, s.pinMap)

# Latest readings
sysData = {
    'temperature': 0,
    'load': 0,
    'memory': 0
}
envData = {
    'temperature': 0,
    'humidity': 0,
    'pressure':0
    }

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
    draw.text((xpos,  5), 'Temp : ' + format(envData['temperature'], '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(envData['humidity'], '.1f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(envData['pressure'], '.0f') + 'mb',  font=font, fill=255)

def sysScreen(xpos=0):
    draw.text((xpos, 5), 'CPU  : ' + format(sysData['temperature'], '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Load : ' + format(sysData['load'], '1.2f'), font=font, fill=255)
    draw.text((xpos, 45), 'Mem  : ' + format(sysData['memory'], '.1f') + '%',  font=font, fill=255)

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
            self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(envData['temperature'], '.1f') + '&deg;</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(envData['humidity'], '.1f') + '%</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(envData['pressure'], '.0f') + 'mb</td></tr>\n', 'utf-8'))

    def _give_sys(self):
        # Internal Sensors
        self.wfile.write(bytes('<tr><th>Server</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + format(sysData['temperature'], '.1f') + '&deg;</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + format(sysData['load'], '1.2f') + '</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + format(sysData['memory'], '.1f') + '%</td></tr>\n', 'utf-8'))

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

    def _give_homelink(self):
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes('<tr>\n', 'utf-8'))
        self.wfile.write(bytes('<td colspan="0" style="text-align: center;"><a href="./">Home</a></td>\n', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))
        self.wfile.write(bytes('</table>\n', 'utf-8'))

    def _give_log(self, lines=10):
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

    def _give_graphs(self, d):
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
        # Process requests and parse their options
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
                body = rrd.drawGraph(duration, graph, s.graphWide, s.graphHigh, s.areaC, s.areaW, s.lineC, s.lineW, s.serverName)
            if (len(body) == 0):
                self.send_error(404, 'Graph unavailable', 'Check your parameters and try again, see the "/graphs/" page for examples.')
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
            self._give_homelink()
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            self._give_graphs(duration)
            self.wfile.write(bytes('</table>', 'utf-8'))
            self._give_homelink()
            self._give_datetime()
            self._give_foot(refresh=300)
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
                self._give_homelink()
                self._give_log()
                self._give_homelink()
                if "deco" in view: self._give_datetime()
                self._give_foot(refresh = 60, scroll = True) 
            else:
                if "deco" in view: 
                    self.wfile.write(bytes('<br>', 'utf-8'))
                    self._give_datetime()
                self._give_foot(refresh = 60)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at "/" and "/graphs"')

    def do_HEAD(self):
        self._set_headers()

def updateData():
    # Runs every few seconds to get current environmental and system data
    if haveSensor:
        envData['temperature'] = bme280.temperature
        envData['humidity'] = bme280.relative_humidity
        envData['pressure'] = bme280.pressure
    sysData['temperature'] = psutil.sensors_temperatures()["cpu_thermal"][0].current
    sysData['load'] = psutil.getloadavg()[0]
    sysData['memory'] = psutil.virtual_memory().percent

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
    rrd.update(envData, sysData, pinState)
    if haveScreen:
        screensaver.check()

def logSensors():
    # Runs on a user defined schedule to dump a line of sensor data in the log
    logLine = ''
    if haveSensor:
        logLine += 'Temp: ' + format(envData['temperature'], '.1f') + degree_sign + ', '
        logLine += 'Humi: ' + format(envData['humidity'], '.0f') + '%, '
        logLine += 'Pres: ' + format(envData['pressure'], '.0f') + 'mb, '
    logLine += 'CPU: ' + format(sysData['temperature'], '.1f') + degree_sign + ', '
    logLine += 'Load: ' + format(sysData['load'], '1.2f') + ', '
    logLine += 'Mem: ' + format(sysData['memory'], '.1f') + '%'
    logging.info(logLine)

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
    # Start by re-nicing to reduce blocking of other processes
    os.nice(10)

    # Set up the button pin interrupt, if defined
    if (s.button_PIN > 0):
        GPIO.setup(s.button_PIN, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(s.button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)
        logging.info('Button enabled')

    # Set all gpio pins to 'output' and record their initial status
    # We need to set them as outputs in our context in order to monitor their state.
    # - So long as we do not try to write to these pins this will not affect their status,
    #   nor will it prevent other processes (eg octoprint) reading and using them
    for i in range(len(s.pinMap)):
        GPIO.setup(s.pinMap[i][1], GPIO.OUT)
        pinState.append(GPIO.input(s.pinMap[i][1]))
        if (pinState[i]):
            logging.info(s.pinMap[i][0] + ": on")
        else:
            logging.info(s.pinMap[i][0] + ": off")

    if (haveScreen):
        # Splash!
        draw.text((10, 10), 'Over-',  font=font, fill=255)
        draw.text((28, 28), 'Watch',  font=font, fill=255)
        show()

    # Do an initial, early, data reading to settle sensors etc
    updateData()

    # Start the web server
    ServeHTTP()

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

    schedule.run_all()  # do the initial log and database update
    scheduleRunDelay(3) # A brief pause for splash

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
