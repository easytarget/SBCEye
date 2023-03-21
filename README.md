# SBCEye : a lightweight monitoring tool for controllers

Monitors my Workshop PI, and lets me see my printroom conditions at a glance via an embeddable web interface and also on a small OLED display. 

It records and displays the CPU temperature, load and memory useage of the SBC itself, plus some other basics. Readings happen every 10 seconds and are held in a database so you can view graphs of how they change with time.

![env](/docs/img/default-main.png)

### Currently Sensor, Display and GPIO features are Raspberry Pi only. Sorry.
You can use an optional BME280 environmental sensor to also record the room temperature, pressure and humidity readings. 

![env](/docs/img/default-bme280.png)

It also has the ability to optionally monitor and log specified GPIO pins as they are toggled by other programs (eg printer power control pins controlled by Octoprint, etc.) and monitor ping times and status for network targets you specify (eg your router, or a wifi enabled controller, etc.)

I have written it to be very low impact on the host; database readings are cached and disk writes only happen every five minutes in order to minimise impact on the SD card. When running without a display the the program typically consumes less than 1% of one CUP core. Adding a display increases this but not by much overall. There is in-built housekeeping to do database backups, dumps and log rotation.

_Bonus!_ Control a light connected to a GPIO pin via a button and/or url, this is a convenience feature I added for myself so I can easily toggle my workbench lamps when in the room, or remotely via the web when viewing my webcams.

Written in Python as a learning excercise, it draws heavily on [RRDtool](https://pypi.org/project/rrdtool/), [RPI.GPIO](https://pypi.org/project/RPi.GPIO/), [psutil](https://pypi.org/project/psutil/), the default python [http.server](https://docs.python.org/3/library/http.server.html) and [CircuitPython](https://github.com/adafruit/circuitpython) for interfacing with sensor and screen.

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
I need to flesh this out in a sepaerate document.

In brief: Customising should be relatively easy, add a data source and commands to gather it in `SBCEye.py` (see how this is done for the CPU temperature, etc); then add it to the graph structures in `robin.py` and the sensorlist in `httpserver.py`. Customising the screens for an OLED display can be done in `animate.py`

## Wiring:
The sensor, display and GPIO control is all optional. The unit itself can only control a single pin, but it can monitor and log multiple pins if you are also using GPIO for controlling other aparatus (eg 3d printer power supplies)
* I2C goes to the 0.96' OLED screen and BME280 Sensor module
* GPIO outputs controlling lights etc; opto-isolated relay boards are your friend here.
* Button goes to a spare GPIO with a pulldown resistor

![schematic](/docs/img/SBCEye-hardware-small.png)

## Plans
I want to add an extensible alerting function.. see [#15](https://github.com/easytarget/SBCEye/issues/15)

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html
https://circuitpython.readthedocs.io/projects/framebuf/en/latest/api.html
https://circuitpython.readthedocs.io/projects/bme280/en/latest/api.html
