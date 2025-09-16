import gpiod
import logging
from os import getpid
from re import search

# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
if int(search('^[0-9]+', gpiod.__version__).group(0)) < 2:
    raise ImportError('gpiod bindings library version too low ({}), '\
                      'pinreader requires gpiod v2.x.x or later.'
                      .format(gpiod.__version__))
'''
PinReader class (dict)
'''
OUTPUT   = gpiod.line.Direction.OUTPUT
ACTIVE   = gpiod.line.Value.ACTIVE
INACTIVE = gpiod.line.Value.INACTIVE

def checkPin(chip, line):
    # chip: (str) gpiod chip (path or identifier)
    # line: (int) Line offset on chip
    if not gpiod.is_gpiochip_device(chip):
        raise ValueError('\'{}\' is not a valid GPIO device'.format(chip))
    gpiochip = gpiod.Chip(chip)
    if line < 0 or line >= gpiochip.get_info().num_lines:
        raise ValueError('Requested line ({}) outside range for \'{}\' ({} lines)'
                         .format(line, chip, gpiochip.get_info().num_lines))
    info = gpiochip.get_line_info(line)
    if info.used == True:
        logging.warning('Could not get pin {}:{} for output, already used by: \'{}\''
                        .format(chip, line, info.consumer))
        return False
    return True

def setPin(chip, line, value):
    # chip:  (str) gpiod chip (path or identifier)
    # line:  (int) Line offset on chip
    # value: (int) 1 = Active, 0 = Inactive
    if value == 0:
        value = INACTIVE
    elif value == 1:
        value = ACTIVE
    else:
        raise ValueError('Invalid output value: {} ({})' .format(value, type(value)))
    try:
        with gpiod.Chip(chip).request_lines(
                 consumer='pinwriter-{}'.format(getpid()),
                 config={line: gpiod.LineSettings(
                         direction = OUTPUT,
                         output_value = value)},
                 ) as request:
            newval = request.get_values()[0]
    except OSError as e:
        # log a warning and return 'False' if the write fails
        logging.warning('Could not set output value on pin {}:{} : {}'
                        .format(chip, line, e))
        return False
    return True if newval == value else False
