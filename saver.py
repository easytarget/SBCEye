'''Implements a screen saver/inverter for the pi overwatch

Requires the python schedule module:
    https://schedule.readthedocs.io/en/stable/
    $ pip install schedule
'''

import time
import schedule

class Saver:
    '''Saver class:
    Turns the display on/off between specified times
    Can also invert the display as a form of burn-in protection

    modes:
        'off': Screensaver disabled
        'blank': Turn screen off
        'invert': Invert the screen

    parameters:
        disp: display driver object
        settings: (tuple) consisting of:
            mode:   (str)  One of 'off', 'blank', 'invert'
            start:  (int)  Start time, hour, 0-23
            end:    (int)  End time, hour, 0-23
            invert: (bool) Base invert state for the display
                           Optional, defaults to False
    '''

    active = False  # Current state

    def __init__(self, disp, settings):

        self.disp = disp
        (self.mode, start, end, *invert) = settings
        self.invert = False
        if len(invert) == 1:
            self.invert = invert[0]
        if self.mode != 'off':
            print(f'Saver will {self.mode} display between: '\
                    f'{start}:00 and {end}:00')
            if (start == end)\
                    or start not in range(0,23)\
                    or end not in range(0,23):
                print('start/end times identical or out of range; disabling')
                self.mode = 'off'
            elif start < end:
                self.saver_map = [False]*24
                for i in range(start, end):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(end, start):
                    self.saver_map[i] = False
            schedule.every().hour.at(":00").do(self.check)
            self.check()


    def _apply_state(self, state):
        '''Apply the desired state to the display'''
        if state:
            self.active = True
            print('Saver activated')
            if self.mode == 'invert':
                self.disp.invert(not self.invert)
            elif self.mode == 'blank':
                self.disp.poweroff()
        else:
            self.active = False
            print('Saver deactivated')
            if self.mode == 'invert':
                self.disp.invert(self.invert)
            elif self.mode == 'blank':
                self.disp.poweron()

    def check(self):
        '''Check the current state vs the time, and apply changes as
        needed. Called on the hour by the scheduler'''
        if self.mode != 'off':
            hour = time.localtime()[3]
            if self.active != self.saver_map[hour]:
                self._apply_state(self.saver_map[hour])
