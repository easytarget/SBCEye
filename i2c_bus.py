'''I2C hardware driver initialisation

Needed by the optional Bus based devices.
Gracefully fails and disables services as appropriate if anything goes wrong
'''
# pragma pylint: disable=import-outside-toplevel

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
            import smbus2
        except ImportError as error:
            print(error)
            print("ERROR: I2C bus requirements (smbus2) not met", flush=True)
            return None

        # Now the I2C device driver object
        try:
            i2c = smbus2.SMBus(settings.bus_id)
        except ValueError as error:
            print(error)
            print("No I2C bus, display and sensor functions will be disabled", flush=True)
            return None

        print('I2C bus found', flush=True)
    return i2c
