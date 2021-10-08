import time

class saver:
    # Current screensaver state
    active = False

    def __init__(self, disp, mode, start, end, invert):
        self.disp = disp
        self.mode = mode
        self.start = start
        self.end = end
        self.invert = invert
        print("mode: " + str(self.mode))
        print("start: " + str(self.start))
        print("end: " + str(self.end))

    def _apply_state(self, state):
        if (state):
            self.active = True
            if (self.mode == 'invert'):
                print("invert")
                self.disp.invert(not self.invert)
            elif (self.mode == 'blank'):
                print("blank")
                self.disp.poweroff()
        else:
            self.active = False
            if (self.mode == 'invert'):
                print("de-invert")
                self.disp.invert(self.invert)
            elif (self.mode == 'blank'):
                print("de-blank")
                self.disp.poweron()

    def check(self):
        if (self.mode != 'off'):
            hour = time.localtime()[4]
            print("SaverIndex: " + str(hour) + " State: " + str(self.active))
            if ((hour == self.start) and not self.active):
                self._apply_state(True)
            elif ((hour == self.end) and self.active):
                self._apply_state(False)
