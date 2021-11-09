# Directly read pins via the /sys/class/gpio tree

from os import path

gpio_root = '/sys/class/gpio'
export_handle = f'{gpio_root}/export'
unexport_handle = f'{gpio_root}/unexport'

def get_pin(pin):
    gpio_handle = f'{gpio_root}/gpio{str(pin)}'
    exported = path.isdir(gpio_handle)
    if not exported:
        with open(export_handle, 'w') as export:
            export.write(str(pin))
    with open(f'{gpio_handle}/value', 'r') as value:
            ret = int(value.read())
    if not exported:
        with open(unexport_handle, 'w') as unexport:
            unexport.write(str(pin))
    return int(ret)
