'''Bus based environmental sensor initialisation
'''
# pragma pylint: disable=import-outside-toplevel

import importlib.util

def oled_setup(settings):
    '''Import and initialise ssd1306 library, return the display object
    uses the 'luma' library, which in turn requires smbus2

    parameters:
        settings: settings oject (from load_config)
    returns:
        disp: Display module object, or None if failed
    '''

    disp = None
    if settings.have_display:
        # I2C OLED Display
        # Uses the ssd1306 driver and libs from the luma libraries
        #  https://github.com/rm-hull/luma.core
        #  https://github.com/rm-hull/luma.oled
        # pip install luma.core luma.oled
        try:
            from luma.oled.device import ssd1306
        except ImportError as error:
            print(error)
            print("ERROR: ssd1306 display requirements not met", flush=True)
            return None

        # for luma display rotation must be specified at init,
        # (value from 0 to 3, rotating 90 degrees each step)
        rotate = 2 if settings.display_rotate else 0
        try:
            # Create the display object
            disp = ssd1306(rotate=rotate)
            print("SSD1306 i2c display found", flush=True)
        except Exception as error:
            print(error)
            print("ERROR: SSD1306 i2c display failed to initialise, disabling", flush=True)
            return None

        # check in advance that the full luma library is available, and not
        # just the display driver. This is used by the animator
        if not importlib.util.find_spec("luma"):
            print("ERROR: Luma library not found, disabling display", flush=True)
            return None
    return disp

if __name__ == "__main__":
    from sys import exit
    print('OLED display class for SBCEye, see inline docs')
    exit()

