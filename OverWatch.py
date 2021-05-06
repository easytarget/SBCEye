#! /usr/bin/python
# Animate the SSD1306 display attached to my OctoPrint server

import time
import subprocess
import logging

from board import SCL, SDA
import busio

# I2C 128x64 OLED Display
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# BME280 I2C Tepmerature Pressure and Humidity sensor
import adafruit_bme280

# GPIO light control
import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO

# Exit Handler
import atexit

passes = 4       # number of (1 second) refreshes of a screen before moving to next
slidespeed = 8   # number of rows to scroll on each animation step
button_PIN = 27  # Lamp button
lamp_PIN = 7     # Lamp relay

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

# Remember the current state of the lamp pin
lampState = GPIO.input(lamp_PIN)

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

# Used when displaying items
degree_sign= u'\N{DEGREE SIGN}'

# Commands used to gather CPU data
cpuCmd = "cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.1f\", $1/1000}'"
topCmd = "top -bn1 | grep load | awk '{printf \"%.3f\", $(NF-2)}'"
memCmd = "free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2 }'"

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
    # Gather BME280 sensor data.
    TMP = bme280.temperature
    HUM = bme280.relative_humidity
    PRE = bme280.pressure
    # Write Data
    draw.text((xpos,  5), 'Temp : ' + format(TMP, '.1f') + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Humi : ' + format(HUM, '.0f') + '%', font=font, fill=255)
    draw.text((xpos, 45), 'Pres : ' + format(PRE, '.0f') + 'mb',  font=font, fill=255)

def sysScreen(xpos=0):
    # Shell commands to grab and parse system data
    CPU = subprocess.check_output(cpuCmd, shell=True).decode("utf-8")
    TOP = subprocess.check_output(topCmd, shell=True).decode("utf-8")
    MEM = subprocess.check_output(memCmd, shell=True).decode("utf-8")
    # Write data.
    draw.text((xpos, 5), 'CPU  : ' + CPU + degree_sign,  font=font, fill=255)
    draw.text((xpos, 25), 'Load : ' + TOP, font=font, fill=255)
    draw.text((xpos, 45), 'Mem  : ' + MEM + '%',  font=font, fill=255)

def buttonInterrupt(channel):
    # Read the lamp and toggle it..
    logging.info('Button pressed')
    if (GPIO.input(lamp_PIN) == True):
        GPIO.output(lamp_PIN,False)
    else:
        GPIO.output(lamp_PIN,True)

def logger():
    global lampState
    global logTimer
    # Check if the lamp has changed state, and log if so
    if (GPIO.input(lamp_PIN) != lampState):
        if (GPIO.input(lamp_PIN) == True):
            logging.info('Lamp ON')
            lampState = True
        else:
            logging.info('Lamp OFF')
            lampState = False
    # Now check if logtimer exceeded, and log parameters if so
    if (time.time() > logTimer+logInterval):
        logDetails()
        logTimer = time.time()

def logDetails():
    TMP = bme280.temperature
    HUM = bme280.relative_humidity
    PRE = bme280.pressure
    CPU = subprocess.check_output(cpuCmd, shell=True).decode("utf-8")
    TOP = subprocess.check_output(topCmd, shell=True).decode("utf-8")
    MEM = subprocess.check_output(memCmd, shell=True).decode("utf-8")
    logging.info('Temp: ' + format(TMP, '.1f') + degree_sign + ', Humi: ' + format(HUM, '.0f') + '%, Pres: ' + format(PRE, '.0f') + 'mb, CPU: ' + CPU + degree_sign + ', Load: ' + TOP + ', Mem: ' + MEM + '%')

def goodBye():
    logging.info('Exiting')

# User Settings

# The fun starts here:

# Set up the lamp interrupt
GPIO.add_event_detect(button_PIN, GPIO.RISING, buttonInterrupt, bouncetime = 400)

logging.info("Init Complete, entering main loop")
atexit.register(goodBye)

# Main loop runs forever
while True:
    # Screen 1
    for i in range(passes):
        clean()
        bmeScreen()
        show()
        logger();
        time.sleep(1)
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
        time.sleep(1)
    # Final update and transition to screen 1
    sysScreen()
    bmeScreen(width+margin)
    logger();
    slideout()
