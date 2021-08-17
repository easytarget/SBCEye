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
hostname = "10.0.0.120"
port = 7080
passtime = 2     # time between read/display cycles
passes = 3       # number of refreshes of a screen before moving to next
slidespeed = 16  # number of rows to scroll on each animation step
button_PIN = 27  # Lamp button
lamp_PIN = 7     # Lamp relay
daisy_PIN = 8      # Temporary, need better solution for multiple pins
sunflower_PIN = 25 # ..ditto

# Logging setup
logInterval = 60
print("Starting OverWatch")
logging.basicConfig(filename='/var/log/overwatch.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%d-%m-%Y %H:%M:%S')
logging.info('')
logging.info("Starting OverWatch")
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

# GPIO setup
GPIO.setmode(GPIO.BCM)           # Set's GPIO pins to BCM GPIO numbering
GPIO.setup(button_PIN, GPIO.IN)  # Set our button pin to be an input
GPIO.setup(lamp_PIN, GPIO.OUT)   # Set our lamp pin to be an output
GPIO.setup(daisy_PIN, GPIO.OUT)       # Set pin to be an output
GPIO.setup(sunflower_PIN, GPIO.OUT)   # Set pin to be an output

# Remember the current state of the lamp pin
lampState = GPIO.input(lamp_PIN)
daisyState = GPIO.input(daisy_PIN)
sunflowerState = GPIO.input(sunflower_PIN)

# Image canvas
margin = 20   # Space between the screens while transitioning
width  = disp.width
span   = width*2 + margin
height = disp.height

# Create image canvas (with mode '1' for 1-bit color)
image = Image.new("1", (span, height))

# Get drawing object so we can easily draw on canvas.
draw = ImageDraw.Draw(image)

# Nice font.
# the LiberationMono-Regular font used here is located in:
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

# Initial values for the sensor readings, this is crude (globals) and should be done better..
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
    CPU = subprocess.check_output(cpuCmd, shell=True).decode("utf-8")
    TOP = subprocess.check_output(topCmd, shell=True).decode("utf-8")
    MEM = subprocess.check_output(memCmd, shell=True).decode("utf-8")

def getLampState():
        if (GPIO.input(lamp_PIN)):
            return "on"
        else:
            return "off"

def getDaisyState():
        if (GPIO.input(daisy_PIN)):
            return "on"
        else:
            return "off"

def getSunflowerState():
        if (GPIO.input(sunflower_PIN)):
            return "on"
        else:
            return "off"

def buttonInterrupt(channel):
    # Read the lamp and toggle it..
    logging.info('Button pressed')
    if (GPIO.input(lamp_PIN) == True):
        GPIO.output(lamp_PIN,False)
    else:
        GPIO.output(lamp_PIN,True)

def ServeHTTP():
    # Spawns a http.server.HTTPServer in a separate thread on the given port.
    handler = _BaseRequestHandler
    httpd = http.server.HTTPServer((hostname, port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well; left here to make this more obvious.
    httpd.allow_reuse_address = True
    threadlog("HTTP server will bind to port " + str(port) + " on host " + hostname)
    httpd.server_bind()
    address = "http://%s:%d" % (httpd.server_name, httpd.server_port)
    threadlog("HTTP server listening on:" + address)
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
    #Wrapper function around logging.info() that prepends the current thread name
    logging.info("[" + current_thread().name + "] : " + logline)

class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):
    # BaseHTTPRequestHandler

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        getBmeData()
        getSysData()
        timestamp = datetime.datetime.now()
        self._set_headers()
        self.wfile.write(bytes('<html>\n<head><meta charset="utf-8">', "utf-8"))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">', "utf-8"))
        self.wfile.write(bytes("<title>%s Overwatch</title>" % ServerName, "utf-8"))
        self.wfile.write(bytes("<style>", "utf-8"))
        self.wfile.write(bytes("body {display:flex; flex-direction: column; align-items: center;}", "utf-8"))
        self.wfile.write(bytes("</style>", "utf-8"))
        self.wfile.write(bytes("</head>", "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
        self.wfile.write(bytes("<h2>%s OverWatch</h2>" % ServerName, "utf-8"))
        self.wfile.write(bytes('<p style="color:grey">' + timestamp.strftime("%H:%M:%S, %A, %d %B, %Y") + '</p>', "utf-8"))
        self.wfile.write(bytes('<table style="border-spacing: 1em;">', "utf-8"))
        self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Room</th></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(TMP, '.1f') + '&deg;</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(HUM, '.0f') + '%</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(PRE, '.0f') + 'mb</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">Server</th></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + CPU + '&deg;</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + TOP + '</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + MEM + '%</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><th style="font-size: 110%; text-align: left;">GPIO</th></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Lamp</td><td>' + getLampState() + '</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Daisy</td><td>' + getDaisyState() + '</td></tr>', "utf-8"))
        self.wfile.write(bytes('<tr><td>Sunflower</td><td>' + getSunflowerState() + '</td></tr>', "utf-8"))
        self.wfile.write(bytes('</table>', "utf-8"))
        self.wfile.write(bytes('<br><pre style="color:grey">GET: %s</pre>' % self.path, "utf-8"))
        self.wfile.write(bytes("</body>", "utf-8"))
        self.wfile.write(bytes("<script>", "utf-8"))
        self.wfile.write(bytes("setTimeout(function(){location.replace(document.URL);}, 60000);", "utf-8"))
        self.wfile.write(bytes("</script>", "utf-8"))
        self.wfile.write(bytes("</html>", "utf-8"))

    def do_HEAD(self):
        self._set_headers()

def logger():
    global lampState
    global daisyState
    global sunflowerState
    global logTimer
    # Check if the lamp has changed state, and log if so
    if (GPIO.input(lamp_PIN) != lampState):
        if (GPIO.input(lamp_PIN) == True):
            logging.info('Lamp ON')
            lampState = True
        else:
            logging.info('Lamp OFF')
            lampState = False
    # Check if daisy has changed state, and log if so
    if (GPIO.input(daisy_PIN) != daisyState):
        if (GPIO.input(daisy_PIN) == True):
            logging.info('Daisy ON')
            daisyState = True
        else:
            logging.info('Daisy OFF')
            daisyState = False
    # Check if sunflower has changed state, and log if so
    if (GPIO.input(sunflower_PIN) != sunflowerState):
        if (GPIO.input(sunflower_PIN) == True):
            logging.info('Sunflower ON')
            sunflowerState = True
        else:
            logging.info('Sunflower OFF')
            sunflowerState = False
    # Now check if logtimer exceeded, and log parameters if so
    if (time.time() > logTimer+logInterval):
        logDetails()
        logTimer = time.time()

def logDetails():
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

    # Set up the lamp interrupt
    GPIO.add_event_detect(button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)

    # Show initial pin states
    logging.info('Lamp: ' + getLampState())
    logging.info('Daisy: ' + getDaisyState())
    logging.info('Sunflower: ' + getSunflowerState())

    logging.info("Entering main loop")
    atexit.register(goodBye)

    # Main loop runs forever
    while True:
        # Screen 1
        for i in range(passes):
            clean()
            bmeScreen()
            show()
            logger();
            time.sleep(passtime)
        # Final update and transition to screen 2
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
        # Final update and transition to screen 1
        sysScreen()
        bmeScreen(width+margin)
        logger();
        slideout()
