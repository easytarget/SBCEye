'''Bus based environmental sensor initialisation
    currently assumes a BME280 (temp/press/humi) sensor
'''
# pragma pylint: disable=import-outside-toplevel

def bme_setup(i2c, settings):
    '''Import and initialise BME sensor library, return the sensor object

    parameters:
        i2c: i2c bus object
        settings: settings oject (from load_config)
    returns:
        bme: Sensor module object, or None if failed
    '''

    bme = None
    if settings.have_sensor:
        # BME280 I2C Tepmerature Pressure and Humidity sensor
        # Uses pimoroni library:
        #  https://github.com/pimoroni/bme280-python
        #  pip install pimoroni-bme280
        try:
            import bme280
        except ImportError as error:
            print(error)
            print("ERROR: BME280 environment sensor requirements not met", flush=True)
            return None

        try:
            # Create the I2C BME280 sensor object and get initial readings
            bme = bme280.BME280(i2c_addr=settings.sensor_addr, i2c_dev=i2c)
        except Exception as error:
            print(error)
            print("We do not have a environmental sensor", flush=True)
            return None

        try:
            # Try initial reading of sensor, bus errors can cause this to fail
            bme.update_sensor()
        except Exception as error:
            print(error)
            print("Environmental sensor failed initial update, this may be due to bus errors", flush=True)
            return None

        print("BME280 sensor found", flush=True)
    return bme
