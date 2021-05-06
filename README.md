# Transmog Overlord Python Script

Runs the HAT and printer PSU controls on a RasPI that also runs 2x Octoprint and 2x webcam; my printroom in a box.

Based on [CircuitPython](https://github.com/adafruit/circuitpython)

### Requires: 

* https://github.com/adafruit/Adafruit_CircuitPython_SSD1306
* https://github.com/adafruit/Adafruit_CircuitPython_BME280

### Docs for CP libs:
https://circuitpython.readthedocs.io/en/latest/shared-bindings/index.html


### Set Up as Service
```
pi@transmog:~/HAT/Transmog-Control $ sudo cp OverWatch.service /etc/systemd/system/

pi@transmog:~/HAT/Transmog-Control $ systemctl status OverWatch.service
● OverWatch.service - My test service
   Loaded: loaded (/etc/systemd/system/OverWatch.service; disabled; vendor preset: enabled)
   Active: inactive (dead)

pi@transmog:~/HAT/Transmog-Control $ sudo systemctl start OverWatch.service

pi@transmog:~/HAT/Transmog-Control $ systemctl status OverWatch.service
● OverWatch.service - My test service
   Loaded: loaded (/etc/systemd/system/OverWatch.service; disabled; vendor preset: enabled)
   Active: active (running) since Thu 2021-05-06 17:54:28 CEST; 3s ago
 Main PID: 20496 (python3)
    Tasks: 2 (limit: 1600)
   CGroup: /system.slice/OverWatch.service
           └─20496 /usr/bin/python3 /home/pi/HAT/Transmog-Control/OverWatch.py
```
