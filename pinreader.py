'''Really simple and direct reading of BCM GPIO pins

provides:
    Pinreader: A class to update and log the pin statuses
    get_pin(pin): reads a bcm gpio pin and returns it's raw value
'''

import os
import logging

GPIO_ROOT = '/sys/class/gpio'
export_handle = f'{GPIO_ROOT}/export'
unexport_handle = f'{GPIO_ROOT}/unexport'

class Pinreader:
    '''Read and update pin status

    Reads the currrent (boolean) status of a set of gipo pins defined in a dictionary
    Updates the relevant entries in data{} and logs state changes

    parameters:
        settings: (tuple) consisting of:
            map: (dict) pin names and BCM GPIO number
            state_names: (tuple) localised names for pin states (text,text)
        data: the main data{} dictionary, a key/value pair; 'pin-<name>=value'
            will be added to it and the vaue updated with pin state changes.

    provides:
        update_pins(): processes and updates the pins
    '''

    def __init__(self, settings, data):
        '''Setup and do initial reading'''
        (self.map, self.state_names) = settings
        self.data = data
        if not self.map:
            print('No GPIO pins configured for monitoring')
            return
        for pin_name, pin_number in self.map.items():
            data[f'pin-{pin_name}'] = get_pin(pin_number)
            logging.info(f'{pin_name}: {self.state_names[data[f"pin-{pin_name}"]]}')
        print('GPIO monitoring configured and logging enabled')
        logging.info('GPIO monitoring configured and logging enabled')

    def update_pins(self):
        '''Check if any pins have changed state, and log if so
        updates the main data{} dictionary with new state
        no parameters, no return'''
        for name, pin in self.map.items():
            this_pin_state =  get_pin(pin)
            if this_pin_state != self.data[f"pin-{name}"]:
                # Pin has changed state, store new state and log
                self.data[f'pin-{name}'] = this_pin_state
                logging.info(f'{name}: {self.state_names[this_pin_state]}')

def get_pin(pin):
    '''Read pin state, return an integer

    parameters:
    pin: (int) the BCM gpio pin number

    returns:
    pin_state: (int) 0=low, 1=high
    '''
    gpio_handle = f'{GPIO_ROOT}/gpio{str(pin)}'
    exported = os.path.isdir(gpio_handle)
    if not exported:
        export = os.open(export_handle, os.O_WRONLY)
        os.write(export, bytes(str(pin), 'ascii'))
        os.close(export)
    value = os.open(f'{gpio_handle}/value', os.O_RDONLY)
    ret = int(os.read(value,1))
    os.close(value)
    if not exported:
        unexport = os.open(unexport_handle, os.O_WRONLY)
        os.write(unexport, bytes(str(pin), 'ascii'))
        os.close(unexport)
    return int(ret)
