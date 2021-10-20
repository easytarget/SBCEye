import time
import logging

class Saver:
    # Current screensaver state
    active = False

    def __init__(self, s, disp):
        self.disp = disp
        self.mode = s.saver_mode
        self.invert = s.saver_invert
        if self.mode != 'off':
            print('Saver will ' + self.mode + ' display between: ' +
                str(s.saver_on) + ':00 and ' + str(s.saver_off) + ':00')
            if (s.saver_on == s.saver_off) or \
               (s.saver_on < 0) or (s.saver_on > 23) or (s.saver_off < 0) or (s.saver_off > 23):
                logging.warning("Saver start/end times are identical or out of range; disabling")
                print("Disabling saver due to invalid time settings")
                self.mode = 'off'
            elif s.saver_on < s.saver_off:
                self.saver_map = [False]*24
                for i in range(s.saver_on, s.saver_off):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(s.saver_off, s.saver_on):
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
