#!/usr/bin/python

# Some general functions we will use
#import os
#import time
#import sys
#import logging
#from logging.handlers import RotatingFileHandler
#import random
#import textwrap
#import schedule

# Local classes
#from saver import Saver
#from robin import Robin


# SHOULD NOT BE NEEDED, WE NEED TO PASS A LIST OF 'screens' TO THE CLASS LATER..
#HAVE_SENSOR = settings.have_sensor

from PIL import Image, ImageDraw, ImageFont

# Unicode degrees character used for display and logging
DEGREE_SIGN= u'\N{DEGREE SIGN}'

class Screen:
    def __init__(self, settings, disp):
        # Create the I2C SSD1306 OLED object
        # The first two parameters are the pixel width and pixel height.
        try:
            disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
        except exception as e:
            print(e)
            print('The display could not be initialised, '\
                    'Display features disabled')
            return HAVE_SCREEN = False
        disp.contrast(settings.display_contrast)
        disp.invert(settings.display_invert)
        # Blank as fast in case it is showing garbage
        disp.fill(0)
        # Splash!
        draw.text((10, 10), 'Over-',  font=font, fill=255)
        draw.text((28, 28), 'Watch',  font=font, fill=255)
        disp.show()
        print("We have a ssd1306 display at address " + hex(disp.addr))

        # Display setup
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
        screensaver = Saver(s, disp)
        logging.info('Display configured and enabled')


    # Draw a black filled box to clear the canvas.
    def _clean():
        draw.rectangle((0,0,span-1,height-1), outline=0, fill=0)

    # Put a specific area of the canvas onto display
    def _show(xpos=0):
        if settings.rotate_display:
            disp.image(image.transform((width,height),
                       Image.EXTENT,(xpos,0,xpos+width,height))
                       .transpose(Image.ROTATE_180))
        else:
            disp.image(image.transform((width,height),
                       Image.EXTENT,(xpos,0,xpos+width,height)))
        disp.show()

    # Slide the display view across the canvas to animate between screens
    def _slideout(step=settings.slidespeed):
        x_pos = 0
        while x_pos < width + margin:
            show(x_pos)
            x_pos = x_pos + step
        show(width + margin)

    # Draw screen for environmental data
    def _bme_screen(xpos=0):
        # Dictionary specifying (name,format,suffix and Y-position)
        items = {
                "env-temp": ('Temp', '.1f', DEGREE_SIGN, 5),
                "env-humi": ('Humi', '.0f', '%', 25),
                "env-pres": ('Pres', '.0f', 'mb', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in data.keys():
                line = f'{name}: {data[sense]:{fmt}}{suffix}'
                draw.text((xpos, ypos), line, font=font, fill=255)
        return '_sys_screen'

    def _sys_screen(self, xpos=0):
        # Dictionary specifying (name,format,suffix and Y-position)
        items = {
                "sys-temp": ('CPU', '.1f', DEGREE_SIGN, 5),
                "sys-load": ('Load', '1.2f', '', 25),
                "sys-mem": ('Mem', '.1f', '%', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in data.keys():
                line = f'{name}: {data[sense]:{fmt}}{suffix}'
                draw.text((xpos, ypos), line, font=font, fill=255)
        return '_bme_screen'

    def update(self):
        # Main loop now runs forever
        while True:
            if HAVE_SCREEN:
                if HAVE_SENSOR:
                    # Environment Screen
                    for this_passp in range(settings.passes):
                        clean()
                        bme_screen()
                        show()
                        scheduler_servicer(settings.passtime)
                    # Update and transition to system screen
                    bme_screen()
                    sys_screen(width+margin)
                    slideout()
                    scheduler_servicer(settings.passtime)
                    # System screen
                    for this_pass in range(settings.passes):
                        clean()
                        sys_screen()
                        show()
                        scheduler_servicer(settings.passtime)
                    # Update and transition back to environment screen
                    sys_screen()
                    bme_screen(width+margin)
                    slideout()
                    scheduler_servicer(settings.passtime)
                else:
                    # Just loop refreshing the system screen
                    for i in range(settings.passes):
                        clean()
                        sys_screen()
                        show()
                        scheduler_servicer(settings.passtime)
            else:
                # No screen, so just run schedule jobs in a loop
                scheduler_servicer()
