#
# Import bus based hardware drivers

# currently only for I2C bus devices, but leaves room for expansion/alternatives

def i2c_setup(screen, sensor):

    disp = None
    bme280 = None

    if screen or sensor:
        # I2C Comms
        try:
            from board import SCL, SDA
            import busio
        except Exception as e:
            print(e)
            print("ERROR: I2C bus requirements not met")
            screen = sensor = False

    if screen:
        # I2C 128x64 OLED Display
        try:
            import adafruit_ssd1306
        except Exception as e:
            print(e)
            print("ERROR: ssd1306 display requirements not met")
            screen = False

    if sensor:
        # BME280 I2C Tepmerature Pressure and Humidity sensor
        try:
            import adafruit_bme280
        except Exception as e:
            print(e)
            print("ERROR: BME280 environment sensor requirements not met")
            sensor = False

    #
    # Initialise the hardware

    if screen or sensor:
        try:
            # Create the I2C interface object
            i2c = busio.I2C(SCL, SDA)
            print('We have a I2C bus')
        except Exception as e:
            print(e)
            print("No I2C bus, display and sensor functions will be disabled")
            screen = sensor = False

    if screen:
        try:
            # Create the I2C SSD1306 OLED object
            # The first two parameters are the pixel width and pixel height.
            disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
            print("We have a ssd1306 display at address " + hex(disp.addr))
        except Exception as e:
            print(e)
            print("We do not have a display")

    if sensor:
        try:
            # Create the I2C BME280 sensor object
            bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
            print("BME280 sensor found with address 0x76")
        except Exception as e:
            try:
                bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
                print("BME280 sensor found with address 0x77")
            except Exception as f:
                print(e)
                print(f)
                print("We do not have a environmental sensor")

    return disp, bme280
