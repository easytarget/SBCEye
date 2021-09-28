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
![Web](/docs/WebDisplay.png)

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
* [pythonRRDtool](https://pythonhosted.org/rrdtool/index.html)

## Install:
* Install the Python3 gpio, schedule and rrdtool packages
  * `sudo apt install python3-rpi.gpio python3-schedule python3-rrdtool`
* Install the CircuitPython libraries listed above
  * These will pull in the python CircuitPython dependencies too
  * `sudo pip3 install adafruit-circuitpython-ssd1306`
  * `sudo pip3 install adafruit-circuitpython-bme280`
* Make sure the `pi` user is in the `gpio` group:
  * `sudo usermod -a -G gpio pi`
* (As the 'pi' user) make a folder `mkdir ~/HAT` and cd into that `cd ~/HAT` 
* Clone this repo:
  * `git clone https://github.com/easytarget/pi-overwatch.git`
* `cd pi-overwatch` into the cloned repo and edit `OverWatch.py` with your gpio settings etc; see the comments near the top of the file.
* Test and run locally with `python3 overwatch.py`
* Set up as a service (below) to run in background at system start

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html

### Set Up as Service
```
pi@transmog:~/HAT/pi-overwatch $ sudo cp OverWatch.service /etc/systemd/system/
pi@transmog:~/HAT/pi-overwatch $ sudo systemctl daemon-reload
pi@transmog:~/HAT/pi-overwatch $ sudo systemctl enable OverWatch.service
pi@transmog:~/HAT/pi-overwatch $ sudo systemctl start OverWatch.service

pi@transmog:~/HAT/pi-overwatch $ sudo systemctl status OverWatch.service
● OverWatch.service - OverWatch script for PI Hat
   Loaded: loaded (/etc/systemd/system/OverWatch.service; enabled; vendor preset: enabled)
   Active: active (running) since Fri 2021-09-17 13:25:07 CEST; 3s ago
 Main PID: 31995 (python3)
    Tasks: 3 (limit: 1600)
   CGroup: /system.slice/OverWatch.service
           └─31995 /usr/bin/python3 /home/pi/HAT/pi-overwatch/OverWatch.py

```
