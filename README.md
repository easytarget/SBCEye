# Transmog Overlord Python Script

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
* Make a folder `~pi/HAT`
* Clone this repo into that `git clone https://easytarget.org/ogit/owen/Transmog-Control.git`
* Make a logfile at `/var/log/overwatch.log`
* test and run with `python overwatch.py`
* set up as a service (below) to run in background as a service

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html


### Set Up as Service
```
pi@transmog:~/HAT/Transmog-Control $ sudo systemctl status OverWatch.service
Unit OverWatch.service could not be found.

pi@transmog:~/HAT/Transmog-Control $ sudo cp OverWatch.service /etc/systemd/system/
pi@transmog:~/HAT/Transmog-Control $ sudo systemctl daemon-reload
pi@transmog:~/HAT/Transmog-Control $ sudo systemctl enable OverWatch.service
pi@transmog:~/HAT/Transmog-Control $ sudo systemctl start OverWatch.service

pi@transmog:~/HAT/Transmog-Control $ sudo systemctl status OverWatch.service
● OverWatch.service - OverWatch script for PI Hat
   Loaded: loaded (/etc/systemd/system/OverWatch.service; enabled; vendor preset: enabled)
   Active: active (running) since Fri 2021-09-17 13:25:07 CEST; 3s ago
 Main PID: 31995 (python3)
    Tasks: 3 (limit: 1600)
   CGroup: /system.slice/OverWatch.service
           └─31995 /usr/bin/python3 /home/pi/HAT/Transmog-Control/OverWatch.py

```