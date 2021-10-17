import time
import logging

class Saver:
    # Current screensaver state
    active = False

    def __init__(self, disp, mode, start, end, invert):
        self.disp = disp
        self.mode = mode
        self.invert = invert
        if self.mode != 'off':
            print('Saver will ' + self.mode + ' display between: ' + str(start) + ":00 and " + str(end) + ":00")
            if (start == end) or (start < 0) or (start > 23) or (end < 0) or (end > 23):
                logging.warning("Saver start/end times are identical or out of range (0-23), disabling saver")
                print("Disabling saver due to invalid time settings")
                self.mode = 'off'
            elif start < end:
                self.saver_map = [False]*24
                for i in range(start, end):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(end, start):
                    self.saver_map[i] = False


    def _apply_state(self, state):
        if state:
            self.active = True
            print("Saver activated")
            if self.mode == 'invert':
                self.disp.invert(not self.invert)
            elif self.mode == 'blank':
                self.disp.poweroff()
        else:
            self.active = False
            print("Saver deactivated")
            if self.mode == 'invert':
                self.disp.invert(self.invert)
            elif self.mode == 'blank':
                self.disp.poweron()

    def check(self):
        if self.mode != 'off':
            hour = time.localtime()[3]
            if self.active != self.saver_map[hour]:
                self._apply_state(self.saver_map[hour])
