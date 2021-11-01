# Some general functions we will use
import logging
import schedule
from PIL import Image, ImageDraw, ImageFont

# Local classes
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
        self.span   = self.width*2 + self.margin
        self.height = self.disp.height

        self.display_rotate = settings.display_rotate
        self.animate_speed = settings.animate_speed

        # Create image canvas (with mode '1' for 1-bit color)
        self.image = Image.new("1", (self.span, self.height))

        # Get drawing object so we can easily draw on canvas.
        self.draw = ImageDraw.Draw(self.image)

        # LiberationMono-Regular : nice font that looks clear on the small display
        # This font is located in: /usr/share/fonts/truetype/liberation/ on Raspian.
        # If you get an error that it is not present, install it with:
        #   sudo apt install fonts-liberation
        self.font = ImageFont.truetype('LiberationMono-Regular.ttf', 16)

        # Splash!
        self.draw.text((10, 10), 'Over-',  font=self.font, fill=255)
        self.draw.text((28, 28), 'Watch',  font=self.font, fill=255)
        self.disp.show()

        # Screen list
        self.screen_list = ['_sys_screen']
        if any(key.startswith("env-") for key in self.data):
            self.screen_list .append('_bme_screen')
        print(f'SCREEN LIST = {self.screen_list}')
        # Start saver
        screensaver = Saver(settings, disp)
        schedule.every(60).seconds.do(screensaver.check)

        logging.info('Display configured and enabled')


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
                "env-temp": ('Temp', '.1f', DEGREE_SIGN, 5),
                "env-humi": ('Humi', '.0f', '%', 25),
                "env-pres": ('Pres', '.0f', 'mb', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in self.data.keys():
                line = f'{name}: {self.data[sense]:{fmt}}{suffix}'
                self.draw.text((xpos, ypos), line, font=self.font, fill=255)

    def _sys_screen(self,xpos=0):
        # Draw screen for system data
        items = {
                "sys-temp": ('CPU', '.1f', DEGREE_SIGN, 5),
                "sys-load": ('Load', '1.2f', '', 25),
                "sys-mem": ('Mem', '.1f', '%', 45),
                }
        for sense,(name,fmt,suffix,ypos) in items.items():
            if sense in self.data.keys():
                line = f'{name}: {self.data[sense]:{fmt}}{suffix}'
                self.draw.text((xpos, ypos), line, font=self.font, fill=255)

    def update(self):
        # UNUSED: WE WILL PUT THE STEP_BY_STEP ANIMATOR HERE
        while True:
            if HAVE_SCREEN:
                if HAVE_SENSOR:
                    # Environment Screen
                    for this_passp in range(settings.animate_passes):
                        clean()
                        bme_screen()
                        show()
                        scheduler_servicer(settings.animate_passtime)
                    # Update and transition to system screen
                    bme_screen()
                    sys_screen(width+margin)
                    slideout()
                    scheduler_servicer(settings.animate_passtime)
                    # System screen
                    for this_pass in range(settings.animate_passes):
                        clean()
                        sys_screen()
                        show()
                        scheduler_servicer(settings.animate_passtime)
                    # Update and transition back to environment screen
                    sys_screen()
                    bme_screen(width+margin)
                    slideout()
                    scheduler_servicer(settings.animate_passtime)
                else:
                    # Just loop refreshing the system screen
                    for i in range(settings.animate_passes):
                        clean()
                        sys_screen()
                        show()
                        scheduler_servicer(settings.animate_passtime)
            else:
                # No screen, so just run schedule jobs in a loop
                scheduler_servicer()
