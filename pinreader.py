# Directly read pins via the /sys/class/gpio tree

from os import path, open, close, read, write, O_WRONLY, O_RDONLY

gpio_root = '/sys/class/gpio'
export_handle = f'{gpio_root}/export'
unexport_handle = f'{gpio_root}/unexport'

def get_pin(pin):
    '''Read pin state, return an integer

    parameters:
    pin: (int) the BCM gpio pin number

    returns:
    pin_state: (int) 0=low, 1=high
    '''
    gpio_handle = f'{gpio_root}/gpio{str(pin)}'
    exported = path.isdir(gpio_handle)
    if not exported:
        export = open(export_handle, O_WRONLY)
        write(export, bytes(str(pin), 'ascii'))
        close(export)
    value = open(f'{gpio_handle}/value', O_RDONLY)
    ret = int(read(value,1))
    close(value)
    if not exported:
        unexport = open(unexport_handle, O_WRONLY)
        write(unexport, bytes(str(pin), 'ascii'))
        close(unexport)
    return int(ret)
