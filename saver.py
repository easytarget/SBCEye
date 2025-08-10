'''Implements a screen saver for the SBCEye project
'''

import time
import logging

class Saver:
    '''Saver class:
    Turns the display on/off between specified times

    modes:
        'off': Screensaver disabled
        'blank': Turn screen off

    parameters:
        disp: display driver object
        settings: (tuple) consisting of:
            mode:   (str)  One of 'off', 'blank'
            start:  (int)  Start time, hour, 0-23
            end:    (int)  End time, hour, 0-23
    '''

    active = False  # Current state

    def __init__(self, disp, settings):

        self.disp = disp
        (self.mode, start, end) = settings
        if self.mode != 'off':
            logging.info(f'Saver will {self.mode} display between: '\
                    f'{start:02d}:00 and {end:02d}:00')
            print(f'Saver will {self.mode} display between: '\
                    f'{start:02d}:00 and {end:02d}:00',flush=True)
            if (start == end)\
                    or start not in range(0,23)\
                    or end not in range(0,23):
                logging.warning('start/end times identical or out of range; disabling saver')
                print('start/end times identical or out of range; disabling saver',flush=True)
                self.mode = 'off'
            elif start < end:
                self.saver_map = [False]*24
                for i in range(start, end):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(end, start):
                    self.saver_map[i] = False
            self.check()


    def _apply_state(self, state):
        '''Apply the desired state to the display'''
        if state:
            self.active = True
            if self.mode == 'blank':
                print('Saver activated',flush=True)
        else:
            self.active = False
            if self.mode == 'blank':
                print('Saver deactivated',flush=True)

    def check(self):
        '''Check the current state vs the time, and apply changes as
        needed.'''
        if self.mode != 'off':
            hour = time.localtime()[3]
            if self.active != self.saver_map[hour]:
                self._apply_state(self.saver_map[hour])
