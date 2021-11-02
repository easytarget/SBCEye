import time

class Saver:
    active = False  # Current state

    def __init__(self, settings, disp):
        self.disp = disp
        self.mode = settings.saver_mode
        self.invert = settings.display_invert
        if self.mode != 'off':
            print(f'Saver will {self.mode} display between: '\
                    f'{settings.saver_on}:00 and {settings.saver_off}:00')
            if (settings.saver_on == settings.saver_off)\
                    or settings.saver_on not in range(0,23)\
                    or settings.saver_off not in range(0,23):
                print('start/end times identical or out of range; disabling')
                self.mode = 'off'
            elif settings.saver_on < settings.saver_off:
                self.saver_map = [False]*24
                for i in range(settings.saver_on, settings.saver_off):
                    self.saver_map[i] = True
            else:
                self.saver_map = [True]*24
                for i in range(settings.saver_off, settings.saver_on):
                    self.saver_map[i] = False
        self.check()


    def _apply_state(self, state):
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
        if self.mode != 'off':
            hour = time.localtime()[3]
            if self.active != self.saver_map[hour]:
                self._apply_state(self.saver_map[hour])
