'''Monitor, record and log GPIO pin changes using gpiod

provides:
    GPIOReader: A class to update and log the pin statuses
'''

import os
import logging
try:
    from pinreader import PinReader
    readerfail = None
except ImportError as e:
    # remember why we failed, so it can be reported in log later.
    readerfail = e

class GPIOReader:
    '''Read and update GPIO pin status

    Reads the currrent (boolean) status of a set of gipo pins defined in a dictionary
    Updates the relevant entries in data{} and logs state changes

    parameters:
        pinlist: dictionary of pin definitions {label: (chip,index)} from config,
            this will be passed directly to the PinReader init.
        data: the main data{} dictionary, a key/value pair; 'pin-<name>=value'
            will be added to it and the vaue updated with pin state changes.

    provides:
        update_pins(): processes and updates the pins
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
        self.directions = {}
        self.consumers = {}
        for pin in self.pins:
            data[f'pin-{pin}'] = self._value_to_data(self.pins[pin].value)
            self.directions[pin] = self.pins[pin].direction
            self.consumers[pin] = self.pins[pin].consumer
            print('Pin \'{}\': {}'.format(pin, repr(self.pins[pin])[12:-1]))
            logging.info('Pin \'{}\': {}'.format(pin, repr(self.pins[pin])[12:-1]))
        print('GPIO monitoring configured and logging enabled')
        logging.info('GPIO monitoring configured and logging enabled')
        self.available = True

    def _value_to_data(self, value):
        return 'U' if value is None else int(value)

    def update(self):
        '''Check if any pins have changed state, and log if so
        updates the main data{} dictionary with new state
        no parameters, no return'''
        self.pins.update()
        for pin in self.pins:
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

