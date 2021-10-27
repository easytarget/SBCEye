# All hail the PI Python OverWatch

Monitors my Workshop PI, and lets me see my printroom conditions at a glance via an embeddable web interface and also on a small OLED display. 

It records and displays the CPU temperature, load and memory useage of the Pi itself, and uses an (optional) environmental sensor to also record the room temperature, pressure and humidity readings

It also has the ability to (optionally) monitor and log specified GPIO pins as they are toggled by other programs (eg printer power control pins controlled by Octoprint, etc.)

_Bonus!_ Control a light connected to a GPIO pin via a button and/or url, useful in the room or if you have webcams.

Written in Python as a learning excercise, it draws heavily on [RRDtool](https://pypi.org/project/rrdtool/), [RPI.GPIO](https://pypi.org/project/RPi.GPIO/), [psutil](https://pypi.org/project/psutil/), the default python [http.server](https://docs.python.org/3/library/http.server.html) and [CircuitPython](https://github.com/adafruit/circuitpython) for interfacing with sensor and screen.

## A Picture is Worth a Thousand Words

Default Web Interface

![env](/docs/default-main.png)![env](/docs/default-graphs.png)

Add a BME280 sensor and/or some GPIO pins to monitor

![bme280](/docs/pihat-bme280-thumb.jpg)
![Web](/docs/workshop-main.png)![Web](/docs/workshop-graphs.png)

Add a 128x64 OLED display

![env](/docs/pihat-env-thumb.jpg)![sys](/docs/pihat-sys-thumb.jpg)

Log GPIO actions etc..

![Web](/docs/workshop-log.png)

Embeddable Panels and Standalone Graphs

![Web](/docs/workshop-sys-panel.png)
![Web](/docs/workshop-humi-graph.png)

## Requires:
* [Python3.7+](https://www.python.org/), [pip](https://pypi.org/project/pip/) and [virtualenv](https://pypi.org/project/virtualenv/)

The [install guide](VENV.md) covers installing these, and the rest of the requirements:
* [Schedule](https://github.com/dbader/schedule)
* [python RRDtool](https://pythonhosted.org/rrdtool/index.html)
* [psutil](https://psutil.readthedocs.io/en/latest/)
* [CircuitPython BME280](https://github.com/adafruit/Adafruit_CircuitPython_BME280)
* [CircuitPython SSD_1306](https://github.com/adafruit/Adafruit_CircuitPython_SSD1306)
* [image](https://pypi.org/project/image/)
* [Liberation Fonts](https://en.wikipedia.org/wiki/Liberation_fonts)

## Install:
This is covered in detail in [this guide](VENV.md)
- Install is done via a python virtual environment to avoid any conflicts with other Python installs (such as OctoPrint)

## Wiring:
The sensor, display and GPIO control is all optional. The unit itself can only control a single pin, but it can monitor and log multiple pins if you are also using GPIO for controlling other aparatus (eg 3d printer power supplies)
* I2C goes to the 0.96' OLED screen and BME280 Sensor module
* GPIO outputs controlling lights etc; opto-isolated relay boards are your friend here.
* Button goes to a spare GPIO with a pulldown resistor

![schematic](/docs/OverWatch-hardware-small.png)

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html
https://circuitpython.readthedocs.io/projects/framebuf/en/latest/api.html
https://circuitpython.readthedocs.io/projects/bme280/en/latest/api.html
