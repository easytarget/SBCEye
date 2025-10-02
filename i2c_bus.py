'''I2C hardware driver initialisation

Needed by the optional Bus based devices.
Gracefully fails and disables services as appropriate if anything goes wrong
'''
# pragma pylint: disable=import-outside-toplevel

def i2c_pin_consume(settings):
    '''Consume the specified pins with a gpiod request to prevent
       other gpio processes from modifying them'''
    if len(settings.bus_lock) != 3:
        return None
    try:
        import gpiod
    except ImportError:
        print('WARNING: Cannot lock I2C pins, gpiod library unavailable')
        return None
    chip = settings.bus_lock[0]
    lines = tuple(settings.bus_lock[1:])
    if not gpiod.is_gpiochip_device(chip):
        print('WARNING: Cannot lock I2C pins, \'{}\' is not a gpiodchip device'\
              .format(chip))
        return None
    try:
        lock = gpiod.request_lines(chip,
                    consumer='{}'.format(settings.identifier),
                    config={lines:None})
    except Exception as e:
        print('WARNING: Cannot lock I2C pins, request failed:\n{}'\
              .format(e))
        return None
    print('I2C bus pins locked (\'{}\': {})'.format(chip, lines))
    return lock


def i2c_setup(settings):
    '''Import and start the I2C bus device

    parameters:
        settings: settings (from load_config)
    returns:
        i2c: Bus driver object, or None if failed
    '''

    # Load the correct modules, be graceful if that fails
    i2c = None
    if settings.have_display or settings.have_sensor:
        # I2C Comms
        # Uses standard SMBUS lib (currently smbus2)
        try:
            from smbus2 import SMBus
        except ImportError as error:
            print(error)
            print("ERROR: I2C bus requirements (smbus2) not met", flush=True)
            return None, None
        # Lock the bus pins if necesscary
        lock = i2c_pin_consume(settings)
        # Now the I2C device driver object
        try:
            i2c = SMBus(settings.bus_id)
        except ValueError as error:
            print(error)
            print("No I2C bus, display and sensor functions will be disabled", flush=True)
            return None, None
        print('I2C bus found', flush=True)
    return i2c, lock
