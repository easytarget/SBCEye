'''Really simple and direct reading of BCM GPIO pins

provides:
    pinreader.get_pin(pin):
    - pin (int) is the bcm pin number
    - returns an integer, 0 or 1 corresponding to on/off
'''

import os

GPIO_ROOT = '/sys/class/gpio'
export_handle = f'{GPIO_ROOT}/export'
unexport_handle = f'{GPIO_ROOT}/unexport'

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
