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
        self._lines = gpiod.Chip(self._gpio_chip).get_info().num_lines
        print('GPIO chip is "{}" with {} lines'.format(self._gpio_chip, self._lines))
        if not self._test_pins():
            print('gpio monitoring disabled')
            return
        for pin_name, pin_number in self._map.items():
            data[f'pin-{pin_name}'] = get_pin(pin_number)
            logging.info(f'{pin_name}: {self.state_names[data[f"pin-{pin_name}"]]}')
        print('GPIO monitoring configured and logging enabled')
        logging.info('GPIO monitoring configured and logging enabled')
        self.available = True

    def _test_pins(self):
        '''Check the pins listed in the pin map'''
        # could check in range of the gpio chip device..
        if len(self._map) == 0:
            print('No valid GPIO pins listed in config, ', end='')
            return False
        return True

    def update_pins(self):
        '''Check if any pins have changed state, and log if so
        updates the main data{} dictionary with new state
        no parameters, no return'''
        return   # <------------------------------------DEBUG
        for name, pin in self.map.items():
            this_pin_state =  get_pin(pin)
            if this_pin_state != self.data[f"pin-{name}"]:
                # Pin has changed state, store new state and log
                self.data[f'pin-{name}'] = this_pin_state
                logging.info(f'{name} (gpio-{pin}): {self.state_names[this_pin_state]}')

        with gpiod.request_lines(
            self.chip_path,
            consumer="SBCEye-pinreader",
            config={tuple(line_offsets): None},
        ) as request:
            vals = request.get_values()
            print(vals, type(vals))
            for offset, val in zip(line_offsets, vals):
                if val == gpiod.line.Value.ACTIVE:
                    print("{}={} ".format(offset, 'ON'), end="")
                else:
                    print("{}={} ".format(offset, 'OFF'), end="")
            #print()

