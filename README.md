# SBCEye : a lightweight monitoring tool for controllers

I designed this to monitor my Workshop using the Raspberry PI that also serves as an octoprint server. This lets me see my printroom conditions at a glance via an embedded web interface and also on a small OLED display.

## Core functions

SBCeye records and displays the CPU temperature, load and memory usage of the SBC itself, plus some other system basics. It can also monitor ping times and status for network targets you specify (eg your router, or a wifi enabled controller, etc.)

Readings happen every 10 seconds and are held in a database, it has a built in graph generator and you can view graphs for arbitrary time periods. This tool is designed to provide a 'fine grained' low-level logging for machines that work as controllers, as opposed to the slower but more sophisticated and comprehensive  system health logging supplied by [Munin](https://munin-monitoring.org/) and similar.

![env](/docs/img/default-main.png)

This can be run on any system that supports the Python3 `psutil` package and the rrdb tool. Currently tested on Debian, Fedora and FreeBSD.

## GPIO Functions
### Currently Sensor, Display and GPIO features are Raspberry Pi only. Sorry.

You can use an optional I2C BME280 environmental sensor to also record the room temperature, pressure and humidity readings.

You can display the current status on a small OLED I2C display sharing the same bus as the BME280, this animates through the current status and has a night/screensaver feature.

![env](/docs/img/default-bme280.png)

It also has the ability to optionally monitor and log specified GPIO pins as they are toggled by other programs (eg printer power control pins controlled by Octoprint, etc.)

## Database and ssd wear reduction.

I have written this to be very low impact on the host; database readings are cached and disk writes only happen every five minutes in order to minimize impact on the SD card. There is in-built housekeeping to do database backups, online dumps and log rotation.

_Bonus!_ Control a light connected to a GPIO pin via a button and/or URL, this is a convenience feature I added for myself so I can easily toggle my workbench lamps when in the room, or remotely via the web when viewing my webcams.

Written in Python as a learning exercise, it draws heavily on [RRDtool](https://pypi.org/project/rrdtool/), [RPI.GPIO](https://pypi.org/project/RPi.GPIO/), [psutil](https://pypi.org/project/psutil/), the default python [http.server](https://docs.python.org/3/library/http.server.html) and [CircuitPython](https://github.com/adafruit/circuitpython) for interfacing with sensor and screen.

## A Picture is Worth a Thousand Words

On a PI3b with some network targets, a BME280 sensor and/or some GPIO pins to monitor

![Web](/docs/img/workshop-all.png)

![bme280](/docs/img/pihat-bme280-thumb.jpg)

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
For sensor:
* [CircuitPython BME280](https://github.com/adafruit/Adafruit_CircuitPython_BME280)
For display:
* [CircuitPython SSD_1306](https://github.com/adafruit/Adafruit_CircuitPython_SSD1306)
* [image](https://pypi.org/project/image/)
* [Liberation Fonts](https://en.wikipedia.org/wiki/Liberation_fonts)

## Install:
This is covered in detail here: [docs/INSTALL.md](docs/INSTALL.md)
- Install is done via a python virtual environment to avoid any conflicts with other Python installs (such as OctoPrint)

## Configuration
Copy the `default.ini` file in the repo to `config.ini` and edit..
* All the useful options are commented in the file
* Restart SBCEye to apply any changes

## Customisation and Architecture
I need to flesh this out in a separate document.

In brief: Customizing should be relatively easy, add a data source and commands to gather it in `SBCEye.py` (see how this is done for the CPU temperature, etc); then add it to the graph structures in `robin.py` and the sensorlist in `httpserver.py`. Customizing the screens for an OLED display can be done in `animate.py`

## Wiring:
The sensor, display and GPIO control is all optional. The unit itself can only control a single pin, but it can monitor and log multiple pins if you are also using GPIO for controlling other apparatus (eg 3d printer power supplies)
* I2C goes to the 0.96' OLED screen and BME280 Sensor module
* GPIO outputs controlling lights etc; opto-isolated relay boards are your friend here.
* Button goes to a spare GPIO with a pull-down resistor

![schematic](/docs/img/SBCEye-hardware-small.png)

## Plans
I want to add an extensible alerting function.. see [#15](https://github.com/easytarget/SBCEye/issues/15)

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html
https://circuitpython.readthedocs.io/projects/framebuf/en/latest/api.html
https://circuitpython.readthedocs.io/projects/bme280/en/latest/api.html
