# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
import gpiod
from os import getpid

INPUT  = gpiod.line.Direction.INPUT
ACTIVE  = gpiod.line.Value.ACTIVE

class PinReader(dict):
    '''
    PinReader class (dict)
    A class derived from a dict() that can record and update the status of a list of pins

    '''
    class _instance:
        '''
        class that holds individual pin instance data and exposes an update() method for the pin
        '''
        def __init__(self, chip, line):
            ''' Creates an pin instance object
                Takes the GPIO chip device specifier (path, or identifier with gpiod v2+)
                and line offset '''
            self._pid = getpid()  # record PID of process that called init()
            if not gpiod.is_gpiochip_device(chip):
                raise ValueError('\'{}\' is not a valid GPIO device'.format(chip))
            self.chip = chip
            try:
                self._chip = gpiod.Chip(chip)
            except PermissionError as e:
                raise PermissionError('Cannot access \'{}\': {}' .format(chip, e))
            if line < 0 or line >= self._chip.get_info().num_lines:
                raise ValueError('Requested line ({}) outside range for \'{}\' ({} lines)'
                                 .format(line, chip, self._chip.get_info().num_lines))
            self.line = line
            info = self._chip.get_line_info(self.line)
            self.name = info.name
            self.get()

        def __repr__(self):
            ''' returns a formatted representation of the pin data '''
            consumer = None if self.consumer is None else '\'{}\''.format(self.consumer)
            return '_instance(chip=\'{}\' line={} consumer={} direction=\'{}\' value={})'\
                   .format(self.chip, self.line, consumer, self.direction, self.value)

        def __str__(self):
            ''' returns a formatted string giving direction, consumer and value '''
            consumer = None if self.consumer is None else '\'{}\''.format(self.consumer)
            return 'direction: {}, consumer: {}, value: {}'\
                   .format(self.direction, consumer, self.value)

        def _value(self):
            ''' reads the value of the pin '''
            try:
                with self._chip.request_lines(consumer='pinreader-{}'.format(self._pid),
                                              config={self.line: None}) as request:
                    val = request.get_values()[0]
                return 1 if val == ACTIVE else 0
            except OSError:
                # silently return None if the read fails
                # - there are possible race conditions if this pin is simultaneously
                #   accessed by another program (or instance of this class..) etc.
                return None

        def get(self):
            ''' reads and updates the current status of the pin,
                the value is only read if the pin is unused '''
            line = self._chip.get_line_info(self.line)
            self.direction = 'input' if line.direction == INPUT else 'output'
            if line.used:
                self.consumer = line.consumer
                self.value = None
            else:
                self.consumer = None
                self.value = self._value()
            return self.value

    ''' class init() '''
    def __init__(self, pinlist, tolerant=False):
        ''' Main class init():
            Takes a pin list: a dictionary{} of pin labels, each item being a tuple()
             of gpio chip path, and line offset.
            The 'tolerant' flag prevents exceptions if an invalid pin is specified '''
        super().__init__({})
        self.chips = []
        for label in pinlist:
            try:
                super().__setitem__(label, self._instance(*pinlist[label]))
            except ValueError as e:
                if not tolerant:
                    raise ValueError('failed to set up pin \'{}\': {}'
                                     .format(label, e))
            else:
                if pinlist[label][0] not in self.chips:
                    self.chips.append(pinlist[label][0])

    def update(self, items=None):
        ''' Updates all pins (deault), a pin, or a list of pins '''
        items = [items] if type(items) == str else items
        items = super().keys() if items is None else items
        for line in items:
            super().__getitem__(line).get()

if __name__ == "__main__":
    from sys import exit
    print('PinReader{} class for SBCEye, see inline docs')
    exit()
