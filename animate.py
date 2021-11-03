# Some general functions we will use
import time
import logging
import schedule
from PIL import Image, ImageDraw, ImageFont

# Local classes
import __main__ as main
from saver import Saver

# Unicode degrees character
DEGREE_SIGN= u'\N{DEGREE SIGN}'

class Animator:
    def __init__(self, settings, disp, data):
        # Display setup
        self.disp = disp
        self.data = data

        self.margin = 20           # Space between the screens while transitioning
        self.width  = self.disp.width
        self.height = self.disp.height
        self.span   = self.width*2 + self.margin

        self.display_rotate = settings.display_rotate
        self.animate_speed = settings.animate_speed
        self.time_format = settings.time_format

        # Create image canvas (with mode '1' for 1-bit color)
        self.image = Image.new("1", (self.span, self.height))

        # Get drawing object so we can easily draw on canvas.
        self.draw = ImageDraw.Draw(self.image)

        # LiberationMono-Regular : nice font that looks clear on the small display
        # This font is located in: /usr/share/fonts/truetype/liberation/ on Raspian.
        # If you get an error that it is not present, install it with:
        #   sudo apt install fonts-liberation
        self.font = ImageFont.truetype('LiberationMono-Bold.ttf', 16)
        self.splash_font = ImageFont.truetype('LiberationMono-Bold.ttf', 36)

        # Screen list
        self.screen_list = []
        if any(key.startswith("env-") for key in self.data):
            self.screen_list.append('_bme_screen')
        self.screen_list.append('_sys_screen')

        # Start main animator
        self.passes = settings.animate_passes
        self.current_pass = -3
        self.current_screen = 0
        schedule.every(settings.animate_passtime).seconds.do(self.frame)
        schedule.every().hour.at(":00").do(self._hourly)
        logging.info('Display configured and enabled')
        print('Display configured and enabled')

        # Start saver
        self.screensaver = Saver(settings, disp)

        # Splash!
        # Will be run automagicallly by the scheduled hourly job
        # when the main loop force-runs all schedules during initialisation


    # Draw a black filled box to clear the canvas.
    def _clean(self):
        self.draw.rectangle((0,0,self.span-1,self.height-1), outline=0, fill=0)

    # Put a specific area of the canvas onto display
    def _show(self, xpos=0):
        if self.display_rotate:
            self.disp.image(self.image.transform((self.width,self.height),
                       Image.EXTENT,(xpos,0,xpos+self.width,self.height))
                       .transpose(Image.ROTATE_180))
        else:
            self.disp.image(self.image.transform((self.width,self.height),
                       Image.EXTENT,(xpos,0,xpos+self.width,self.height)))
        self.disp.show()

    def _slideout(self):
        # Slide the display view across the canvas to animate between screens
        x_pos = 0
        while x_pos < self.width + self.margin:
            self._show(x_pos)
            x_pos = x_pos + self.animate_speed
        self._show(self.width + self.margin)

    def _bme_screen(self, xpos=0):
        # Draw screen for environmental data
        items = {
                "env-temp": (' Temp: ', '.1f', DEGREE_SIGN, 5),
                "env-humi": (' Humi: ', '.0f', '%', 25),
                "env-pres": (' Pres: ', '.0f', 'mb', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in self.data.keys():
                line = f'{name}{self.data[sense]:{fmt}}{suffix}'
                self.draw.text((xpos, ypos), line, font=self.font, fill=255)

    def _sys_screen(self,xpos=0):
        # Draw screen for system data
        items = {
                "sys-temp": (' CPU:  ', '.1f', DEGREE_SIGN, 5),
                "sys-load": (' Load: ', '1.2f', '', 25),
                "sys-mem":  (' Mem:  ', '.1f', '%', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in self.data.keys():
                line = f'{name}{self.data[sense]:{fmt}}{suffix}'
                self.draw.text((xpos, ypos), line, font=self.font, fill=255)

    def _splash(self):
        def _text(xpos):
            self.draw.text((8 + xpos, 0), 'Over-',  font=self.splash_font, fill=255)
            self.draw.text((8 + xpos, 30), 'Watch',  font=self.splash_font, fill=255)
        self.current_pass = -3
        self.current_screen = 0
        self.draw.rectangle((self.width + self.margin,0,self.span-1,self.height-1),
                outline=0, fill=0)
        _text(self.width + self.margin)
        self._slideout()
        self._clean()
        _text(0)
        self._show()

    def _hourly(self):
        # totally frivously do a spash screen once an hour.
        self._splash()

    def frame(self):
        # Run from the scheduler, animates each step of the cycle in sequence
        self.current_pass += 1
        if self.current_pass >= self.passes:
            self.current_pass = 0
            self.current_screen += 1
            self.current_screen %= len(self.screen_list)
            getattr(self,self.screen_list[self.current_screen])(self.width + self.margin)
            self._slideout()
        elif self.current_pass >= 0:
            self._clean()
            getattr(self,self.screen_list[self.current_screen])()
            self._show()
        elif self.current_pass == -1:
            getattr(self,self.screen_list[self.current_screen])(self.width + self.margin)
            self._slideout()
