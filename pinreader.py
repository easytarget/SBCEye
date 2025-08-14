'''Really simple and direct reading of BCM GPIO pins

provides:
    Pinreader: A class to update and log the pin statuses
    get_pin(pin): reads a bcm gpio pin and returns it's raw value
'''

import os
import logging
import gpiod

class Pinreader:
    '''Read and update pin status

    Reads the currrent (boolean) status of a set of gipo pins defined in a dictionary
    Updates the relevant entries in data{} and logs state changes

    parameters:
        settings: (tuple) consisting of:
            chip: (str) path to the gpio chip device node, or None to disable
            map: (dict) pin names and BCM GPIO number
            state_names: (tuple) localised names for pin states (text,text)
        data: the main data{} dictionary, a key/value pair; 'pin-<name>=value'
            will be added to it and the vaue updated with pin state changes.

    provides:
        update_pins(): processes and updates the pins
    '''

    def __init__(self, settings, data):
        '''Setup and do initial reading'''
        (self._gpio_chip, self._map, self._state_names) = settings
        self.data = data
        self.available = False
        if self._gpio_chip is None:
            print('No GPIO chip specified in config, gpio monitoring disabled')
            return
        if not gpiod.is_gpiochip_device(self._gpio_chip):
            print('ERROR: GPIO chip specified in config ({}) is not a libgpiod '\
                  'compatible device, gpio monitoring disabled'.format(self._gpio_chip))
            self._gpio_chip = None
            return
        self._num_lines = gpiod.Chip(self._gpio_chip).get_info().num_lines
        print('GPIO chip is "{}" with {} lines'.format(self._gpio_chip, self._num_lines))
        if not self._setup_pins():
            print('No valid GPIO pins listed in config, gpio monitoring disabled')
            return
        values = self._get_pins(self._pins)
        if values is None:
            print('GPIO pin states could not be read, gpio monitoring disabled')
            return
        for index, name, value in zip(self._pins, self._names, values):
            data[f'pin-{name}'] = int(value)
            logging.info('{} index {} configured as "{}", current value: {}'
                        .format(self._gpio_chip, index, name, self._state_names[int(value)]))
        print('GPIO monitoring active and logging enabled')
        logging.info('GPIO monitoring active and logging enabled')
        self.available = True

    def _setup_pins(self):
        '''Check the pins listed in the pin map are validi and create lists'''
        self._pins = []
        self._names = []
        for name, pin in self._map.items():
            if pin > 0 and pin < self._num_lines:
                self._pins.append(pin)
                self._names.append(name)
            else:
                print('ERROR: gpio chip index ({}) for "{}" is out of range'.format(pin, name))
        if len(self._pins) == 0:
            return False
        return True

    def _get_pins(self, pins):
        '''Get the value of all pins using gpiod, do not change pin state'''
        values = []
        try:
            with gpiod.request_lines(
                self._gpio_chip,
                consumer="SBCEye-pinreader",
                config={tuple(pins): None},
            ) as request:
                line_values = request.get_values()
                for value in line_values:
                    if value == gpiod.line.Value.ACTIVE:
                        values.append(int(1))
                    else:
                        values.append(int(0))
        except Exception as e:
            print('Error getting pin values:\n{}'.format(e))
            return None
        return values

    def update_pins(self):
        '''Check if any pins have changed state, and log if so
        updates the main data{} dictionary with new state
        no parameters, no return'''
        # Update current values list
        values = self._get_pins(self._pins)
        if values is None:
            # The try:except in the system log should show the actual errors
            # Some sort of warn/fail tracking might be needed if issues occcur here a lot.
            logging.info('GPIO pin read failed (see syslog)')
            return
        # Now go through pins, store data and see what has changed
        for index, name, value in zip(self._pins, self._names, values):
            if value != self.data[f"pin-{name}"]:
                # Pin has changed state, store new state and log
                self.data[f'pin-{name}'] = value
                logging.info('{} ({}:{}): {}'.format(name, self._gpio_chip, index,
                                                    self._state_names[int(value)]))
