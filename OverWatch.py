# SPDX-FileCopyrightText: 2017 Tony DiCola for Adafruit Industries
# SPDX-FileCopyrightText: 2017 James DeVito for Adafruit Industries
# SPDX-License-Identifier: MIT

# This example is for use on (Linux) computers that are using CPython with
# Adafruit Blinka to support CircuitPython libraries. CircuitPython does
# not support PIL/pillow (python imaging library)!

import time
import subprocess

from board import SCL, SDA
import busio

# I2C Display
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# User Settings
pause = 3  #delay before screen cycles

# Create the I2C interface.
i2c = busio.I2C(SCL, SDA)

# Create the SSD1306 OLED class.
# The first two parameters are the pixel width and pixel height.  Change these
# to the right size for your display!
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

# BME280
import adafruit_bme280

bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)

# The fun starts here:

# Clear display.
disp.fill(0)
disp.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new("1", (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=0)

# Load default font.
# font = ImageFont.load_default()

# Alternatively load a TTF font.  Make sure the .ttf font file is in the
# same directory as the python script!
# Some other nice fonts to try: http://www.dafont.com/bitmap.php
# font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 9)
font = ImageFont.truetype('LiberationMono-Regular.ttf', 16)
degree_sign= u'\N{DEGREE SIGN}'

def slideout(scroll=1):
    x = 127
    while x > 0:
        disp.scroll(scroll,0)
        disp.fill_rect(0, 0, scroll, height, 0)
        disp.show()
        x = x - scroll


while True:

    # Screen 1

    # Draw a black filled box to clear the image.
    draw.rectangle((0,0,width-1,height-1), outline=0, fill=0)

    # Write three lines of BME280 sensor data.
    draw.text((0, 5), 'Temp : ' + format(bme280.temperature, '.1f') + degree_sign,  font=font, fill=255)
    draw.text((0, 25), 'Humi : ' + format(bme280.relative_humidity, '.0f') + '%', font=font, fill=255)
    draw.text((0, 45), 'Pres : ' + format(bme280.pressure, '.0f') + 'mb',  font=font, fill=255)

    # Display image.
    disp.image(image.transpose(Image.ROTATE_180))
    disp.show()
    time.sleep(pause)
    slideout(4)

    # Screen 2

    # Draw a black filled box to clear the image.
    draw.rectangle((0,0,width-1,height-1), outline=0, fill=0)

    # Shell commands to grab system data
    cmd = "cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.1f\", $1/1000}'"
    CPU = subprocess.check_output(cmd, shell=True).decode("utf-8")
    cmd = "top -bn1 | grep load | awk '{printf \"%.3f\", $(NF-1)}'"
    TOP = subprocess.check_output(cmd, shell=True).decode("utf-8")
    cmd = "free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2 }'"
    MEM = subprocess.check_output(cmd, shell=True).decode("utf-8")

    # Write three lines of BME280 sensor data.
    draw.text((0, 5), 'CPU  : ' + CPU + degree_sign,  font=font, fill=255)
    draw.text((0, 25), 'Load : ' + TOP, font=font, fill=255)
    draw.text((0, 45), 'Mem  : ' + MEM + '%',  font=font, fill=255)

    # Display image.
    disp.image(image.transpose(Image.ROTATE_180))
    disp.show()
    time.sleep(pause)
    slideout(4)
