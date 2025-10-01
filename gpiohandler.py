'''Monitor, record and log GPIO pin changes using gpiod

provides:
    GPIOReader: A class to update and log the pin statuses
'''

import gpiod
import logging
from os import getpid
from re import search

# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
if int(search('^[0-9]+', gpiod.__version__).group(0)) < 2:
    readerfail = 'gpiod bindings library version too low ({}), '\
                      'pinreader requires gpiod v2.x.x or later.'\
                      .format(gpiod.__version__)
else:
    readerfail = None
    from pinreader import PinReader

'''
PinReader class (dict)
'''
INPUT  = gpiod.line.Direction.INPUT
OUTPUT  = gpiod.line.Direction.OUTPUT
ACTIVE  = gpiod.line.Value.ACTIVE
INACTIVE  = gpiod.line.Value.INACTIVE


class GPIOHandler:
    '''Read and update GPIO pin status

    Reads the currrent (boolean) status of a set of gipo pins defined in a dictionary
    Updates the relevant entries in data{} and logs state changes

    parameters:
        pinlist: dictionary of pin definitions {label: (chip,index)} from config,
            this will be passed directly to the PinReader init.
        data: the main data{} dictionary, a key/value pair; 'pin-<name>=value'
            will be added to it and the value updated with pin state changes.

    provides:
        update(): processes and updates the pin data, logs state changes
        set_pin(pin,value): attempts to set the output value of a pin
                            - returns success/fail, used for web control
    '''

    def __init__(self, pinlist, data):
        '''Setup and do initial reading'''
        self.available = False
        self.pinlist = pinlist
        self.pins = {}
        self.data = data
        if not self.pinlist:
            print('No GPIO pins configured for monitoring')
            return
        if readerfail:
            print('GPIOD bindings could not be imported: {}\nPin monitoring disabled'
                  .format(readerfail))
            logging.warning('GPIO pins were specified but pinreader failed to import, see syslog')
            logging.info('Pin monitoring disabled')
            return
        try:
            self.pins = PinReader(self.pinlist)
        except Exception as e:
            print('GPIO pin setup failed: {}\nPin monitoring disabled.'.format(e))
            logging.warning('GPIO pins were specified but pin setup failed, see syslog')
            logging.info('Pin monitoring disabled')
            return
        self.directions = {}  # used to remember directions for change detection
        self.consumers = {}   # used to remember consumers for change detection
        for pin in self.pins:
            data[f'pin-{pin}'] = self._value_to_data(self.pins[pin].value)
            self.directions[pin] = self.pins[pin].direction
            self.consumers[pin] = self.pins[pin].consumer
            print('Pin \'{}\': {}'.format(pin, repr(self.pins[pin])[10:-1]))
            logging.info('Pin \'{}\': {}'.format(pin, repr(self.pins[pin])[10:-1]))
        print('GPIO monitoring configured and logging enabled')
        logging.info('GPIO monitoring configured and logging enabled')
        self.available = True

    def _value_to_data(self, value):
        '''Records failed reads as 'U' (unavailable) for data{} entries'''
        return 'U' if value is None else int(value)

    def _update_pin(self, pin):
        '''Check if pin has changed state, log changes and
        update the data{} dictionary with new state'''
        log = ''
        direction = self.pins[pin].direction
        if direction != self.directions[pin]:
            self.directions[pin] = direction
            log += ' direction to: \'{}\','.format(direction)
        consumer = self.pins[pin].consumer
        if consumer != self.consumers[pin]:
            self.consumers[pin] = consumer
            consumer = None if consumer is None else '\'{}\''.format(consumer)
            log += ' consumer to: {},'.format(consumer)
        value = self.pins[pin].value
        if self._value_to_data(value) != self.data[f'pin-{pin}']:
            self.data[f'pin-{pin}'] = self._value_to_data(value)
            log += ' value to: {},'.format(value)
        if len(log) != 0:
            logging.info('Pin \'{}\' changed{}'.format(pin, log.rstrip(',')))
            print('Pin \'{}\' changed{}'.format(pin, log.rstrip(',')))

    def update(self):
        '''Update data{} dictionary for all pins'''
        self.pins.update()
        for pin in self.pins:
            self._update_pin(pin)

    def setPin(self, pin, value):
        '''Sets the pin to output mode and sets it's value.
        Parameters:
            pin: the pin name from config
            value: (int) 1 = Active, 0 = Inactive
        Returns:
            False if the output cannot be set.'''
        if value == 0:
            value = INACTIVE
        elif value == 1:
            value = ACTIVE
        else:
            raise ValueError('Invalid output value: {} ({})'
                             .format(value, type(value)))
        self.pins.update(pin)
        chip = self.pins[pin].chip
        line = self.pins[pin].line
        newval = None
        if self.pins[pin].consumer is not None:
            logging.warning('Failed to set ouput on pin \'{}\', currently used by: \'{}\''
                            .format(pin, self.pins[pin].consumer))
        else:
            try:
                with gpiod.Chip(chip).request_lines(
                         consumer='SBCEye-{}'.format(getpid()),
                         config={line: gpiod.LineSettings(
                                 direction = OUTPUT,
                                 output_value = value)},
                         ) as request:
                    newval = request.get_values()[0]
            except OSError as e:
                # log a warning and return 'False' if the write fails
                logging.warning('Could not set output value on pin {}:{} : {}'
                                .format(chip, line, e))
        self.pins.update(pin)
        self._update_pin(pin)
        return True if newval == value else False

    def makeInput(self, pin):
        '''Sets the pin to input mode and reads it's value to data{} dictionary.
        Parameters:
            pin: the pin name from config'''
        self.pins.update(pin)
        chip = self.pins[pin].chip
        line = self.pins[pin].line
        if self.pins[pin].consumer is not None:
            logging.warning('Failed to set input mode on pin \'{}\', currently used by: \'{}\''
                            .format(pin, self.pins[pin].consumer))
        else:
            try:
                with gpiod.Chip(chip).request_lines(
                         consumer='SBCEye-{}'.format(getpid()),
                         config={line: gpiod.LineSettings(
                                 direction = INPUT)},
                         ) as request:
                    _ = request.get_values()[0]
            except OSError as e:
                # log a warning and return 'False' if the write fails
                logging.warning('Could not set input mode on pin {}:{} : {}'
                                .format(chip, line, e))
        self.pins.update(pin)
        self._update_pin(pin)
        return
