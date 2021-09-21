#! /usr/bin/python
# Animate the SSD1306 display attached to my OctoPrint server

# Start by re-nicing so we dont block anything important
import os
os.nice(10)

# Some general functions we will use
import time
import datetime
import subprocess
import logging
from threading import Thread, current_thread
from logging.handlers import RotatingFileHandler

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

# Exit Handler
import atexit

#
# User Settings
#

# Web UI
host = "10.0.0.120"    # Host ip address for webui
port = 7080            # Port number for webui

# Logging
logInterval = 600       # Logging interval (seconds)
logLines = 512         # How many lines of logging to show in webui

# GPIO
# All pins are defined using BCM GPIO numbering
# https://raspberrypi.stackexchange.com/a/12967

# Button pin (set to `0` to disable button)
button_PIN = 27        # Button

# Pin list
# - List entries consist of ['Name',BCM Pin Number, state]
# - The button, if enabled, will always control the 1st entry)
# - The state will be read from the pins at startup and used to log changes

#pinMap = []   # Gpio Disabled

pinMap = [['Lamp',       7, False],
          ['Sunflower', 25, False],
          ['Daisy',      8, False]]

# Display animation
passtime = 2     # time between read/display cycles
passes = 3       # number of refreshes of a screen before moving to next
slidespeed = 16  # number of rows to scroll on each animation step

# Logging setup
print("Starting OverWatch")
logFile = '/var/log/overwatch.log'
handler = RotatingFileHandler(logFile, maxBytes=1024*1024, backupCount=2)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S', handlers=[handler])
logging.info('')
logging.info("Starting OverWatch")
logCmd = f"for a in `ls -tr {logFile}*`;do cat $a ; done | tail -{logLines}"
logTimer = 0

# Create the I2C interface object
i2c = busio.I2C(SCL, SDA)

# Create the I2C SSD1306 OLED object
# The first two parameters are the pixel width and pixel height.
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
# Immediately blank the display in case it is showing garbage
disp.fill(0)
disp.show()

# Create the I2C BME280 sensor object
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)

# GPIO mode
GPIO.setmode(GPIO.BCM)  # Set's GPIO pins to BCM GPIO numbering

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
# This font is located in:
# /usr/share/fonts/truetype/liberation/ on Raspian.
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
    disp.image(image.transform((width,height),Image.EXTENT,(xpos,0,xpos+width,height)).transpose(Image.ROTATE_180))
    disp.show()

def slideout(step=slidespeed):
    # Slide the display view across the canvas to animate between screens
    x = 0
    while x < width + margin:
        show(x)
        x = x + step
    show(width + margin)

def bmeScreen(xpos=0):
    getBmeData()
    draw.text((xpos,  5), 'Temp : ' + format(TMP, '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(HUM, '.0f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(PRE, '.0f') + 'mb',  font=font, fill=255)

def sysScreen(xpos=0):
    getSysData()
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

def toggleButtonPin():
    # Read the first pin and toggle it..
    if (GPIO.input(pinMap[0][1]) == True):
        GPIO.output(pinMap[0][1],False)
        return "off"
    else:
        GPIO.output(pinMap[0][1],True)
        return "on"

def buttonInterrupt(channel):
    # short delay, then re-read input to provide a hold-down
    # and suppress false triggers from other gpio operations
    time.sleep(0.050)
    if (GPIO.input(button_PIN) == True):
        logging.info('Button pressed')
        toggleButtonPin()
    else:
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
        self.end_headers()

    def _give_head(self, scrolldown = False):
        self.wfile.write(bytes('<html>\n<head><meta charset="utf-8">\n', 'utf-8'))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">\n', 'utf-8'))
        self.wfile.write(bytes('<title>%s Overwatch</title>\n' % ServerName, 'utf-8'))
        self.wfile.write(bytes('<style>\n', 'utf-8'))
        self.wfile.write(bytes('body {display:flex; flex-direction: column; align-items: center;}\n', 'utf-8'))
        self.wfile.write(bytes('</style>\n', 'utf-8'))
        self.wfile.write(bytes('</head>\n', 'utf-8'))
        if (scrolldown):
            self.wfile.write(bytes("<script>\n", 'utf-8'))
            self.wfile.write(bytes('function down() {\n', 'utf-8'))
            self.wfile.write(bytes('    window.scrollTo(0,document.body.scrollHeight);\n', 'utf-8'))
            self.wfile.write(bytes('}\n', 'utf-8'))
            self.wfile.write(bytes('window.onload = down;\n', 'utf-8'))
            self.wfile.write(bytes('</script>\n', 'utf-8'))
        self.wfile.write(bytes('<body>\n', 'utf-8'))

    def _give_foot(self,refresh = False):
            self.wfile.write(bytes('<pre style="color:#888888">GET: ' + self.path + ' from: ' + self.client_address[0] + '</pre>\n', 'utf-8'))
            self.wfile.write(bytes('</body>\n', 'utf-8'))
            if (refresh):
                self.wfile.write(bytes("<script>\n", 'utf-8'))
                self.wfile.write(bytes('setTimeout(function(){location.replace(document.URL);}, 60000);\n', 'utf-8'))
                self.wfile.write(bytes('</script>\n', 'utf-8'))
            self.wfile.write(bytes('</html>\n', 'utf-8'))

    def _give_datetime(self):
        timestamp = datetime.datetime.now()
        self.wfile.write(bytes('<p style="color:#666666">' + timestamp.strftime("%H:%M:%S, %A, %d %B, %Y") + '</p>\n', 'utf-8'))

    def do_GET(self):
        if (self.path == '/log'):
            log = subprocess.check_output(logCmd, shell=True).decode('utf-8')
            self._set_headers()
            self._give_head(scrolldown=True)
            self.wfile.write(bytes('<h2>Overwatch Log:</h2>\n', 'utf-8'))
            self._give_datetime()
            self.wfile.write(bytes('<pre>\n' + log + '<pre>\n', 'utf-8'))
            self.wfile.write(bytes(f'<p>Latest {logLines} lines shown</p>\n', 'utf-8'))
            self._give_foot(refresh=True)
        elif (self.path == '/button'):
            logging.info('Web button triggered by: ' + self.client_address[0])
            state = toggleButtonPin()
            self._set_headers()
            self._give_head()
            self.wfile.write(bytes('<h2>' + pinMap[0][0] + 'Toggled : ' + state + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif(self.path == '/'):
            getBmeData()
            getSysData()
            self._set_headers()
            self._give_head()
            self.wfile.write(bytes('<h2>%s OverWatch</h2>\n' % ServerName, 'utf-8'))
            self._give_datetime()
            self.wfile.write(bytes('<table style="border-spacing: 1em;">\n', 'utf-8'))
            # room sensors
            self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Room</th></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(TMP, '.1f') + '&deg;</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(HUM, '.0f') + '%</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(PRE, '.0f') + 'mb</td></tr>\n', 'utf-8'))
            # Internal Sensors
            self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Server</th></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + CPU + '&deg;</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + TOP + '</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + MEM + '%</td></tr>\n', 'utf-8'))
            # GPIO states
            if (len(pinMap) > 0): 
                self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">GPIO</th></tr>\n', 'utf-8'))
                for pin in pinMap:
                    if (pin[2]):
                        self.wfile.write(bytes('<tr><td>' + pin[0] +'</td><td>on</td></tr>\n', 'utf-8'))
                    else:
                        self.wfile.write(bytes('<tr><td>' + pin[0] +'</td><td>off</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('</table>\n', 'utf-8'))
            self.wfile.write(bytes('<p>\n', 'utf-8'))
            self.wfile.write(bytes('<a href="./log" style="color:#666666; font-weight: bold; text-decoration: none;">View latest Logs</a>\n', 'utf-8'))
            self.wfile.write(bytes('</p>\n', 'utf-8'))
            self._give_foot(refresh=True)
        else:
            self.send_error(404, 'No Such Page', 'This site only serves pages at "/", "/log" and "/button"')

    def do_HEAD(self):
        self._set_headers()

def logger():
    global pinMap
    global logTimer
    # Check if any pins have changed state and log if so 
    for i in range(len(pinMap)):
        if (GPIO.input(pinMap[i][1]) != pinMap[i][2]):
            if (GPIO.input(pinMap[i][1]) == True):
                logging.info(pinMap[i][0] + ' ON')
                pinMap[i][2] = True
            else:
                logging.info(pinMap[i][0] + ' OFF')
                pinMap[i][2] = False
    # Now check if logtimer exceeded, and log sensor readings if so
    if (time.time() > logTimer+logInterval):
        logSensors()
        logTimer = time.time()

def logSensors():
    getBmeData()
    getSysData()
    logging.info('Temp: ' + format(TMP, '.1f') + degree_sign + ', Humi: ' + format(HUM, '.0f') + '%, Pres: ' + format(PRE, '.0f') + 'mb, CPU: ' + CPU + degree_sign + ', Load: ' + TOP + ', Mem: ' + MEM + '%')

def goodBye():
    logging.info('Exiting')

# The fun starts here:
if __name__ == "__main__":
    logging.info("Init Complete")

    # Web Server
    ServerName = "Transmog"
    ServeHTTP()

    # Set all pins to 'output' for the purposes of this script.. 
    #   this wont affect their current state or prevent other processes accessing and setting them
    #   necesscary to allow us to read their current state
    for i in range(len(pinMap)):
        GPIO.setup(pinMap[i][1], GPIO.OUT)
        if (GPIO.input(pinMap[i][1])):
            pinMap[i][2] = True
            logging.info(pinMap[i][0] + ": on")
        else:
            pinMap[i][2] = False
            logging.info(pinMap[i][0] + ": off")

    # Set up the button pin interrupt, otherwise button is disabled
    if (button_PIN > 0):
        GPIO.setup(button_PIN, GPIO.IN)       # Set our button pin to be an input
        GPIO.add_event_detect(button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)
        logging.info('Button enabled')

    logging.info("Entering main loop")
    atexit.register(goodBye)

    # Main loop now runs forever
    while True:
        # Screen 1
        for i in range(passes):
            clean()
            bmeScreen()
            show()
            logger();
            time.sleep(passtime)

        # Update and transition to screen 2
        bmeScreen()
        sysScreen(width+margin)
        logger();
        slideout()

        # Screen 2
        for i in range(passes):
            clean()
            sysScreen()
            show()
            logger();
            time.sleep(passtime)

        # Update and transition to screen 1
        sysScreen()
        bmeScreen(width+margin)
        logger();
        slideout()
