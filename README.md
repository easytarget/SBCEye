# All hail the PI Python OverWatch

Runs the HAT and printer PSU controls on a RasPI that also runs 2x Octoprint and 2x webcam; my printroom in a box.

Based on [CircuitPython](https://github.com/adafruit/circuitpython)

## Pics

![bme280](/docs/pihat-bme280-thumb.jpg)
![env](/docs/pihat-env-thumb.jpg)
![sys](/docs/pihat-sys-thumb.jpg)

## Requires:
* https://github.com/adafruit/Adafruit_CircuitPython_SSD1306
* https://github.com/adafruit/Adafruit_CircuitPython_BME280

## Install:
__In order to access the GPIO reliably I run this script as root, not ideal, I know.__
* Follow the instructions to install the circuitpython libs listed above
  * `sudo pip3 install adafruit-circuitpython-ssd1306`
  * `sudo pip3 install adafruit-circuitpython-bme280`
* As the 'Pi' user make a folder `mkdir ~/HAT` and cd into that `cd ~/HAT` 
* Clone this repo into that `git clone https://github.com/easytarget/pi-overwatch.git`
* cd into that reps and edit `OverWatch.py` with your gpio settings etc, see the comments near the top of the file
* test and run with `sudo python overwatch.py`
* set up as a service (below) to run in background at system start

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html


### Set Up as Service
```
pi@transmog:~/HAT/pi-overwatch $ sudo systemctl status OverWatch.service
Unit OverWatch.service could not be found.

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
