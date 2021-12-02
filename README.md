# All hail the PI Python OverWatch

Monitors my Workshop PI, and lets me see my printroom conditions at a glance via an embeddable web interface and also on a small OLED display. 

It records and displays the CPU temperature, load and memory useage of the Pi itself, and uses an (optional) environmental sensor to also record the room temperature, pressure and humidity readings

It also has the ability to (optionally) monitor and log specified GPIO pins as they are toggled by other programs (eg printer power control pins controlled by Octoprint, etc.)

_Bonus!_ Control a light connected to a GPIO pin via a button and/or url, useful in the room or if you have webcams.

Written in Python as a learning excercise, it draws heavily on [RRDtool](https://pypi.org/project/rrdtool/), [RPI.GPIO](https://pypi.org/project/RPi.GPIO/), [psutil](https://pypi.org/project/psutil/), the default python [http.server](https://docs.python.org/3/library/http.server.html) and [CircuitPython](https://github.com/adafruit/circuitpython) for interfacing with sensor and screen.

## A Picture is Worth a Thousand Words

Default Web Interface

![env](/docs/img/default-main.png)

Add a BME280 sensor and/or some GPIO pins to monitor

![bme280](/docs/img/pihat-bme280-thumb.jpg)
![Web](/docs/img/workshop-main.png)![Web](/docs/img/workshop-graphs.png)

Add a 128x64 OLED display

![env](/docs/img/pihat-env-thumb.jpg)

Log GPIO actions etc..

![Web](/docs/img/workshop-log.png)

Embeddable Panels and Standalone Graphs

![Web](/docs/img/workshop-sys-panel.png)
![Web](/docs/img/workshop-humi-graph.png)

## Requires:
* [Python3.7+](https://www.python.org/), [pip](https://pypi.org/project/pip/) and [virtualenv](https://pypi.org/project/virtualenv/)

The [install guide](docs/INSTALL.md) covers installing these, and the rest of the requirements in a way that wont conflict with other python tools and versions on your system:
* [Schedule](https://github.com/dbader/schedule)
* [python RRDtool](https://pythonhosted.org/rrdtool/index.html)
* [psutil](https://psutil.readthedocs.io/en/latest/)
* [CircuitPython BME280](https://github.com/adafruit/Adafruit_CircuitPython_BME280)
* [CircuitPython SSD_1306](https://github.com/adafruit/Adafruit_CircuitPython_SSD1306)
* [image](https://pypi.org/project/image/)
* [Liberation Fonts](https://en.wikipedia.org/wiki/Liberation_fonts)

## Install:
This is covered in detail here: [docs/INSTALL.md](docs/INSTALL.md)
- Install is done via a python virtual environment to avoid any conflicts with other Python installs (such as OctoPrint)

## Configuration
Copy the `default.ini` file in the repo to `config.ini` and edit..
* All the useful options are commented in the file
* Restart Overwatch to apply any changes

## Customisation and Architecture
I need to flesh this out in a sepaerate document.

In brief: Customising should be relatively easy, add a data source and commands to gather it in `overwatch.py` (see how this is done for the CPU temperature, etc); then add it to the graph structures in `robin.py` and the sensorlist in `httpserver.py`. Customising the screens for an OLED display can be done in `animate.py`

## Wiring:
The sensor, display and GPIO control is all optional. The unit itself can only control a single pin, but it can monitor and log multiple pins if you are also using GPIO for controlling other aparatus (eg 3d printer power supplies)
* I2C goes to the 0.96' OLED screen and BME280 Sensor module
* GPIO outputs controlling lights etc; opto-isolated relay boards are your friend here.
* Button goes to a spare GPIO with a pulldown resistor

![schematic](/docs/img/OverWatch-hardware-small.png)

## Plans
I want to add an extensible alerting function.. see [#15](https://github.com/easytarget/pi-overwatch/issues/15)

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html
https://circuitpython.readthedocs.io/projects/framebuf/en/latest/api.html
https://circuitpython.readthedocs.io/projects/bme280/en/latest/api.html
