'''Bus based hardware drivers
'''

# currently only for I2C bus devices, but leaves room for expansion/alternatives

def i2c_setup(screen, sensor):
    '''Import and start the I2C bus devices'''
    disp = None
    bme280 = None

    # Start by determining if we can load the correct modules
    if screen or sensor:
        # I2C Comms
        try:
            import busio
            from board import SCL, SDA
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
        try:
            import adafruit_bme280
        except ImportError as error:
            print(error)
            print("ERROR: BME280 environment sensor requirements not met")
            sensor = False

    # Now the actual device driver objects
    if screen or sensor:
        try:
            # Create the I2C interface object
            i2c = busio.I2C(SCL, SDA)
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

        try:
            # Additional modules needed for display
            # Not actually used here in the main loop, but we test for them here
            # so we do not get an ugly failure when the display animator loads.
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as error:
            disp = None
            print(error)
            print("ERROR: PIL graphics module not found, disabling display")

    if sensor:
        try:
            # Create the I2C BME280 sensor object
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
            print("BME280 sensor found with address 0x76")
        except RuntimeError as error:
            try:
                bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
                print("BME280 sensor found with address 0x77")
            except RuntimeError as failure:
                print(error)
                print(failure)
                print("We do not have a environmental sensor")

    return disp, bme280
