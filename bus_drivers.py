'''Bus based hardware driver initialisation

Imports and starts the optional Bus based devices.
Gracefully fails and disables services as appropriate if anything goes wrong

I'd probably do this differently if writing from scratch/refactoring, and
make better use of Importlib in overwatch.py.
'''
# pragma pylint: disable=import-outside-toplevel

import importlib.util


def i2c_setup(screen, sensor):
    '''Import and start the I2C bus devices

    parameters:
        screen: (bool) is screen enabled in config?
        sensor: (bool) is environmental sensor (bme280) enabled in config?

    returns:
        disp:   Display driverr object or None if failed
        bme280: Sensor module object, or None if failed
    '''

    disp = None
    bme280 = None

    # Start by trying to load the correct modules
    if screen or sensor:
        # I2C Comms
        # Uses standard SMBUS lib (currently smbus2)
        try:
            import smbus2
        except ImportError as error:
            print(error)
            print("ERROR: I2C bus requirements not met")
            screen = sensor = False

    if screen:
        # I2C 128x64 OLED Display
        try:
            import adafruit_ssd1306
        except ImportError as error:
            print(error)
            print("ERROR: ssd1306 display requirements not met")
            screen = False

    if sensor:
        # BME280 I2C Tepmerature Pressure and Humidity sensor
        # Uses pimoroni library:
        #  https://github.com/pimoroni/bme280-python
        #  pip install pimoroni-bme280
        try:
            import bme280
        except ImportError as error:
            print(error)
            print("ERROR: BME280 environment sensor requirements not met")
            sensor = False

    # Now the actual device driver objects
    if screen or sensor:
        try:
            # Create the I2C interface object
            i2c = smbus2.SMBus(1)
            print('We have a I2C bus')
        except ValueError as error:
            print(error)
            print("No I2C bus, display and sensor functions will be disabled")
            screen = sensor = False

    if screen:
        try:
            # Create the I2C display object
            disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
            print("SSD1306 i2c display found")
        except RuntimeError as error:
            disp = None
            print(error)
            print("ERROR: SSD1306 i2c display failed to initialise, disabling")

        if not importlib.util.find_spec("PIL"):
            disp = None
            print("ERROR: PIL graphics module not found, disabling display")

    if sensor:
        try:
            # Create the I2C BME280 sensor object
            bmeSensor = bme280.BME280(i2c_dev=i2c)
            print("BME280 sensor found")
        except RuntimeError as error:
            print(error)
            print("We do not have a environmental sensor")

    print(flush=True)
    return disp, bmeSensor
