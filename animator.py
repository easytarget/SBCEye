'''Display Animator class and start function
part of the OverWatch Project
'''

# pragma pylint: disable=logging-fstring-interpolation

# Some general functions we will use
from time import sleep
import logging
from sys import exit as sys_exit
from signal import signal, SIGTERM, SIGINT
import schedule
from PIL import Image, ImageDraw, ImageFont

# Local classes
from saver import Saver

# Unicode degrees character
DEGREE_SIGN = u'\N{DEGREE SIGN}'

FRAME_MAP = {
        "bme-screen": {
            "env-temp": ('Temp: ', '.1f', DEGREE_SIGN, 5),
            "env-humi": ('Humi: ', '.0f', '%', 25),
            "env-pres": ('Pres: ', '.0f', 'mb', 45),
            },
        "sys-screen1": {
            "sys-temp": ('CPU:  ', '.1f', DEGREE_SIGN, 5),
            "sys-load": ('Load: ', '1.2f', '', 25),
            "sys-freq": ('Freq: ', '.0f', 'MHz', 45),
            },
        "sys-screen2": {
            "sys-mem":  ('Mem:  ', '.1f', '%', 5),
            "sys-disk": ('Disk: ', '.1f', '%', 25),
            "sys-proc": ('Proc: ', '.0f', '', 45),
            },
        }

class Animator:
    '''Animates the I2C OLED display

    Handles starting the display and then displays the desired information
    screens according to user-defined 'frame' rate.
    Screens are 'slid' into place to provide a pleasing animation effect
    A screensaver can be invoked to blank or invert the display as the user wishes
    '''

    def __init__(self, settings, disp, data):
        '''Display setup'''
        self.disp = disp
        self.data = data

        self.margin = 20           # Space between the screens while transitioning
        self.width  = self.disp.width
        self.height = self.disp.height
        self.span   = self.width*2 + self.margin

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
        try:
            self.font = ImageFont.truetype('LiberationMono-Bold.ttf', 16)
            self.splash_font = ImageFont.truetype('LiberationMono-Bold.ttf', 36)
        except OSError:
            print('"LiberationMono" font not present, falling back to ugly default')
            print('Install font with "$ sudo apt install fonts-liberation"')
            self.font = self.splash_font =  ImageFont.load_default()

        # Begin with empty screen list
        self.screen_list = []

        # Start main animator
        self.passes = settings.animate_passes
        self.current_pass = -2
        self.current_frame = 0
        schedule.every(settings.animate_passtime).seconds.do(self._frame)
        schedule.every().hour.at(":00").do(self._hourly)

        # Start saver
        saver_settings = (settings.saver_mode, settings.saver_on,
                settings.saver_off, settings.display_invert)
        self.screensaver = Saver(disp, saver_settings)
        self.screensaver.check()
        schedule.every().hour.at(":00").do(self.screensaver.check)

        # Notify logs etc
        logging.info('Display configured and enabled')
        print('Display configured and enabled')
        self._splash()


    def _clean(self):
        '''Draw a black filled box to clear the canvas'''
        self.draw.rectangle((0,0,self.span-1,self.height-1), outline=0, fill=0)

    def _show(self, xpos=0):
        '''Put a specific area of the canvas onto display'''
        if self.display_rotate:
            self.disp.image(self.image.transform((self.width,self.height),
                       Image.EXTENT,(xpos,0,xpos+self.width,self.height))
                       .transpose(Image.ROTATE_180))
        else:
            self.disp.image(self.image.transform((self.width,self.height),
                       Image.EXTENT,(xpos,0,xpos+self.width,self.height)))
        self.disp.show()

    def _slideout(self):
        '''Slide the display view across the canvas to animate between screens'''
        x_pos = 0
        while x_pos < self.width + self.margin:
            self._show(x_pos)
            x_pos = x_pos + self.animate_speed
        self._show(self.width + self.margin)

    def _draw_row(self, key, template, xpos):
        '''Draw the supplied row with offset "xpos" using template data
        if the supplied key name does not exist in data, show "N/A"
        '''
        if key in self.data.keys():
            row = f'{template[0]}{self.data[key]:{template[1]}}{template[2]}'
        else:
            row = f'{template[0]}N/A'
        self.draw.text((xpos + 6, template[3]), row, font=self.font, fill=255)

    def _draw_frame(self, frame_data, xpos=0):
        '''Draw the supplied frame with offset "xpos"
        '''
        for key,template in frame_data.items():
            self._draw_row(key, template, xpos)

    def _no_data(self, reason='Initialising'):
        '''Cover screen for when the data structure is empty'''
        def _text(xpos):
            self.draw.text((5 + xpos, 5),
                    'No Data:', font=self.font, fill=255)
            self.draw.text((5 + xpos, 25),
                    reason, font=self.font, fill=255)
        self._clean()
        _text(0)
        self._show()

    def _splash(self):
        ''' Run hourly by the scheduler
        Will be run automagicallly at startup when the main loop
        force-runs all schedules during initialisation'''
        def _text(xpos):
            self.draw.text((8 + xpos, 0), 'Over-',  font=self.splash_font, fill=255)
            self.draw.text((8 + xpos, 28), 'Watch',  font=self.splash_font, fill=255)
        self.current_pass = -1
        self.current_frame = 0
        self.draw.rectangle((self.width + self.margin,0,self.span-1,self.height-1),
                outline=0, fill=0)
        _text(self.width + self.margin)
        self._slideout()
        self._clean()
        _text(0)
        self._show()

    def _update_screen_list(self):
        '''add screens to the list when data for them is available'''
        for screen,rows in FRAME_MAP.items():
            if (rows.keys() & self.data.keys()) and (screen not in self.screen_list):
                self.screen_list.append(screen)

    def _frame(self):
        '''Run from the scheduler, animates each step of the cycle in sequence'''
        self._update_screen_list()
        self.current_pass += 1
        if len(self.screen_list) == 0:
            self._no_data()
        elif self.current_pass >= self.passes:
            # move to next frame
            self.current_pass = 0
            self.current_frame += 1
            self.current_frame %= len(self.screen_list)
            self._draw_frame(FRAME_MAP[self.screen_list[self.current_frame]],
                    self.width + self.margin)
            self._slideout()
        elif self.current_pass > 0:
            # Update current frame
            self._clean()
            self._draw_frame(FRAME_MAP[self.screen_list[self.current_frame]])
            self._show()
        elif self.current_pass == 0:
            # We are transitioning from a splash/alarm screen, slide
            self._draw_frame(FRAME_MAP[self.screen_list[self.current_frame]],
                    self.width + self.margin)
            self._slideout()
        # else:
        #     current_pass is less than 0
        #     leave display as-is, used to display splash, alarms, etc.

    def _hourly(self):
        '''check screensaver and totally frivously do a spash screen once an hour'''
        self.screensaver.check()
        self._splash()


def animate(settings, disp, queue):
    '''Runs in a subprocess, animate the display using data recieved on the queue

    This function is called as a subprocess and is not expected to return.
    It starts the main Animator class, which animates the display and is driven
    by the scheduler to provide animation 'passes'.
    The screensaver is driven by another schedule as needed

    Having started the Animator class this function enters an infinite loop
    servicing the schedule(s) once per second. It listens on a queue
    for incoming data pairs, and updates the values it displays.

    parameters:
        settings: main overwatch settings class
        disp:     display module object
        queue:    multiprocess queue, used to recieve data updates

    returns:
        Nothing, enters a loop and is not expected to return
    '''

    def die_with_dignity(*_):
        '''Exit cleanly (eg without stack trace) on a sigint/sigterm'''
        print('Display animator process exiting')
        sys_exit()

    signal(SIGTERM, die_with_dignity)
    signal(SIGINT, die_with_dignity)

    try:
        # Set a user-friendly process name if possible
        import setproctitle
        process_name = settings.name.encode("ascii", "ignore").decode("ascii")
        setproctitle.setproctitle(f'overwatch screen: {process_name}')
    except ModuleNotFoundError:
        pass

    # Start the animator
    data = {}
    animation = Animator(settings, disp, data)

    # Loop forever servicing scheduler and queue
    while animation:
        while not queue.empty():
            key, value = queue.get_nowait()
            if value:
                data.update({key: value})
            else:
                data.pop(key, None)
        schedule.run_pending()
        sleep(0.25)
