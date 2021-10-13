# All hail the PI Python OverWatch

Lets me see my printroom conditions at a glance on a small OLED display and also via an embeddable web interface. 

It logs temperature, pressure and humidity environmental readings, plus the CPU temperature, load and memory useage of the Pi itself.

(Optionally) It also has the ability to monitor and log specified GPIO pins as they are toggled by other programs (eg printer power control pins controlled by Octoprint, etc.)

_Bonus!_ it can control a light connected to a GPIO pin via a button and/or url, useful if you have webcams..

Based on [CircuitPython](https://github.com/adafruit/circuitpython)

## Pics

![bme280](/docs/pihat-bme280-thumb.jpg)
![env](/docs/pihat-env-thumb.jpg)
![sys](/docs/pihat-sys-thumb.jpg)
![Web](/docs/WebDisplay.png)![Web](/docs/WebGraph.png)

## Wiring
* Needs a diagram
* I2C goes to the 0.96' OLED screen and BME280 Sensor module
* (Optional) Button goes to a spare GPIO with a pulldown resistor:
* (Optional) GPIO output(s)

## Requires:
* Python3.6+
* [CircuitPython SSD_1306](https://github.com/adafruit/Adafruit_CircuitPython_SSD1306)
* [CircuitPython BME280](https://github.com/adafruit/Adafruit_CircuitPython_BME280)
* [Schedule](https://github.com/dbader/schedule)
* [python RRDtool](https://pythonhosted.org/rrdtool/index.html)
* [psutil](https://psutil.readthedocs.io/en/latest/)
* Liberation Fonts

## Install:
This is covered in detail in [this guide](VENV.md)
- Install is done via a python virtual environment to avoid any conflicts with other Python installs (such as OctoPrint)

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html
https://circuitpython.readthedocs.io/projects/framebuf/en/latest/api.html
https://circuitpython.readthedocs.io/projects/bme280/en/latest/api.html
