'''Bus based hardware driver initialisation

Imports and starts the optional Bus based devices.
Gracefully fails and disables services as appropriate if anything goes wrong

I'd probably do this differently if writing from scratch/refactoring, and
make better use of Importlib in overwatch.py.
'''
# pragma pylint: disable=import-outside-toplevel

import importlib.util


def i2c_setup(settings):
    '''Import and start the I2C bus devices

    parameters:
        settings: settings oject (from load_config)
    returns:
        disp:   Display driverr object or None if failed
        bme: Sensor module object, or None if failed
    '''

    # booleans
    sensor = settings.have_sensor
    display = settings.have_display
    # objects to be returned if successful
    disp = None
    bme = None

    # Start by trying to load the correct modules
    if display or sensor:
        # I2C Comms
        # Uses standard SMBUS lib (currently smbus2)
        try:
            import smbus2
        except ImportError as error:
            display = sensor = False
            print(error)
            print("ERROR: I2C bus requirements not met")

    if display:
        # I2C OLED Display
        # Uses the ssd1306 driver and libs from the luma libraries
        #  https://github.com/rm-hull/luma.core
        #  https://github.com/rm-hull/luma.oled
        # pip install luma.core luma.oled
        try:
            from luma.oled.device import ssd1306
        except ImportError as error:
            display = False
            print(error)
            print("ERROR: ssd1306 display requirements not met")

    if sensor:
        # BME280 I2C Tepmerature Pressure and Humidity sensor
        # Uses pimoroni library:
        #  https://github.com/pimoroni/bme280-python
        #  pip install pimoroni-bme280
        try:
            import bme280
        except ImportError as error:
            sensor = False
            print(error)
            print("ERROR: BME280 environment sensor requirements not met")

    # Now the actual device driver objects
    if display or sensor:
        try:
            # Create the I2C interface object
            i2c = smbus2.SMBus(settings.bus_id)
            print('We have a I2C bus')
        except ValueError as error:
            display = sensor = False
            print(error)
            print("No I2C bus, display and sensor functions will be disabled")

    if display:
        # for luma display rotation must be specified here,
        # (value from 0 to 3, rotating 90 degrees each step)
        rotate = 2 if settings.display_rotate else 0
        try:
            # Create the display object
            disp = ssd1306(bus=i2c, address=settings.display_addr, rotate=rotate)
            print("SSD1306 i2c display found")
        except Exception as error:
            disp = None
            print(error)
            print("ERROR: SSD1306 i2c display failed to initialise, disabling")

        if not importlib.util.find_spec("luma"):
            disp = None
            print("ERROR: Luma library not found, disabling display")

    if sensor:
        try:
            # Create the I2C BME280 sensor object and get initial readings
            bme = bme280.BME280(i2c_addr=settings.sensor_addr, i2c_dev=i2c)
        except Exception as error:
            bme = None
            print(error)
            print("We do not have a environmental sensor")

        try:
            # Try initial reading of sensor, bus errors can cause this to fail
            bme.update_sensor()
            print("BME280 sensor found")
        except Exception as error:
            bme = None
            print(error)
            print("Environmental sensor failed initial update, this may be due to bus errors")

    print(flush=True, end='')
    return disp, bme
