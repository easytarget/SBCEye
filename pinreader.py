import gpiod
from os import getpid
from re import search

# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
if int(search('^[0-9]+', gpiod.__version__).group(0)) < 2:
    raise ImportError('gpiod bindings library version too low ({}), '\
                      'pinreader requires gpiod v2.x.x or later.'
                      .format(gpiod.__version__))
'''
PinInstance class

'''
class PinInstance:
    def __init__(self, chip, line):
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
        consumer = None if self.consumer is None else '\'{}\''.format(self.consumer)
        return 'PinInstance(chip=\'{}\' line={} consumer={} direction=\'{}\' value={})'\
               .format(self.chip, self.line, consumer, self.direction, self.value)

    def __str__(self):
        consumer = None if self.consumer is None else '\'{}\''.format(self.consumer)
        return 'direction: {}, consumer: {}, value: {}'\
               .format(self.direction, consumer, self.value)

    def _value(self):
        try:
            with self._chip.request_lines(consumer='pinstance-{}'.format(self._pid),
                                          config={self.line: None}) as request:
                val = request.get_values()[0]
            return 1 if val == gpiod.line.Value.ACTIVE else 0
        except:
            # silently return None if the read fails
            # - there are possible race conditions if this pin is simultaneously
            #   accessed by another program (or instance of this class..) etc.
            return None

    def get(self):
        line = self._chip.get_line_info(self.line)
        self.direction = 'input' if line.direction == gpiod.line.Direction.INPUT else 'output'
        if line.used:
            self.consumer = line.consumer
            self.value = None
        else:
            self.consumer = None
            self.value = self._value()
        return self.value

'''
PinReader class (dict)

'''
class PinReader(dict):
    def __init__(self, pinlist, tolerant=False):
        super().__init__({})
        for label in pinlist:
            try:
                super().__setitem__(label, PinInstance(pinlist[label][0], pinlist[label][1]))
            except ValueError as e:
                if not tolerant:
                    raise ValueError('failed to set up pin \'{}\': {}'
                                     .format(label, e))

    def __str__(self):
        ret = ''
        for line in super().__iter__():
            pin = super().__getitem__(line)
            if pin.value is not None:
                value = 'low' if pin.value == 0 else 'high'
                ret += '{} = {} ({})\n'.format(line, value, pin.direction)
            else:
                ret += '{} = n/a (\'{}\')\n'.format(line, pin.consumer)
        return ret.rstrip('\n')

    def update(self):
        for line in super().keys():
            super().__getitem__(line).get()

'''
    HELPER
'''

def find_pins(device, regex, verbose=False):
    if not gpiod.is_gpiochip_device(device):
        raise ValueError('\'{}\' is not a valid GPIO device'.format(device))
    pinlist = {}
    with gpiod.Chip(device) as chip:
        if verbose:
            print('Searching for pins on \'{}\' that match regex: {}'
                  .format(chip.path, regex))
        for line in range(0, chip.get_info().num_lines):
            name = chip.get_line_info(line).name
            name = str(line) if name is None else name
            if search(regex, name):
                pinlist[name] = (chip.path, line)
                if verbose:
                    print(' adding: \'{}\' (line {})'.format(name, line))
            elif verbose:
                    print(' skipping: \'{}\' (line {})'.format(name, line))
    return pinlist

if __name__ == "__main__":
    '''
        DEMO
    '''

    from sys import argv
    from time import asctime, sleep
    from argparse import ArgumentParser

    self = argv[0]
    desc = 'Display GPIO pin states and value (if availabe) for matching pins '\
           'on the specified gpio chip. Use \'gpioinfo\' to see available pins.'
    elog = 'IMPORTANT: use regex wisely, DO NOT use a generic wildcard such as \'.*\'. '\
           'Requesting pins that are used by the OS may cause conflicts. eg: reading the value '\
           'of pins labelled \'SD_*\' can cause Disk I/O errors on Raspberry PI\'s.)'
    parser = ArgumentParser(prog=self, description=desc, epilog=elog)
    parser.add_argument("-i", "--interval", default=0, help="Interval between updates in seconds, default: 0 (run once)", type=float)
    parser.add_argument("-c", "--chip", default="/dev/gpiochip0", help="GPIO chip device path, default: /dev/gpiochip0", type=str)
    parser.add_argument("-r", "--regex", default="^GPIO[0-9]+$", help="RegEX to select pin names, default: ^GPIO[0-9]+$", type=str)
    parser.add_argument("-v", "--verbose", action="store_true", help="Show chip and regex processing")
    args = parser.parse_args()

    # Seach for pins using the device and regex determined above
    pinlist = find_pins(args.chip, args.regex, args.verbose)
    if len(pinlist) == 0:
        print('No matching pins, exiting')
        exit()

    # Instantiate the pinreader class on this list
    pinstates = PinReader(pinlist)

    # little function to collate output
    def out():
        return '{}: {}\n{}\n'.format(self, asctime(), pinstates)

    # Show initial output
    print(out(), end='')

    # Now loop forever showing the values if needed
    while args.interval != 0:
        sleep(args.interval)
        pinstates.update()
        print("\033[F" * (len(pinstates) + 1), end='')
        for line in out().split('\n')[:-1]:
            print('\033[K{}'.format(line))
