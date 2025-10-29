'''Implements a screen saver for the SBCEye project
'''

import time
import logging

class Saver:
    '''Saver class:
    Turns the display on/off between specified times

    modes:
        'disabled': Screensaver disabled
        'blank': Turn screen off

    parameters:
        disp: display driver object
        settings: (tuple) consisting of:
            mode:   (str)  One of 'disabled', 'blank'
            start:  (int)  Start time, hour, 0-23
            end:    (int)  End time, hour, 0-23

    provides:
        check():  Checks state and applies saver as needed
                  called from a schedule loop by main code
    '''

    active = False  # Current state

    def __init__(self, disp, settings):
        self.disp = disp
        (self.mode, start, end) = settings
        if self.mode != 'disabled':
            if (start == end)\
                or start not in range(0,23)\
                or end not in range(0,23):
                logging.warning('Saver start/end times identical or out of range; disabling')
                print('Saver start/end times identical or out of range; disabling',flush=True)
                self.mode = 'disabled'
            elif start < end:
                self.saver_map = [False]*24
                for i in range(start, end):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(end, start):
                    self.saver_map[i] = False
            logging.info(f'Saver will {self.mode} display between: '\
                    f'{start:02d}:00 and {end:02d}:00')
            print(f'Saver will {self.mode} display between: '\
                    f'{start:02d}:00 and {end:02d}:00',flush=True)
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
        if self.mode != 'disabled':
            hour = time.localtime()[3]
            if self.active != self.saver_map[hour]:
                self._apply_state(self.saver_map[hour])

if __name__ == "__main__":
    from sys import exit
    print('OLED screensaver class for SBCEye, see inline docs')
    exit()

