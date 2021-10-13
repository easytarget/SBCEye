# Installing in virtualenv
* https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/

### Setup

This assumes that you are running a fully updated Raspian install (Buster as of this time of writing) and have python3 installed, and have cloned the repo to `/~/HAT/pi-overwatch` 

```
$ sudo apt install python3 python3-pip
$ mkdir ~/HAT
$ git clone https://github.com/easytarget/pi-overwatch.git ~/HAT/pi-overwatch
(Alternatively, if you have downloaded a zip or tarball, you should unpack it to: ~/HAT/pi-overwatch) 
$ cd ~/HAT/pi-overwatch
```

### Install and Upgrade Requirements

In the cloned repo upgrade our local (user) modules of `pip` and `virtualenv`
```
pi@pi:~/HAT/pi-overwatch $ pwd
/home/pi/HAT/pi-overwatch

pi@pi:~/HAT/pi-overwatch $ python3 -m pip --version
pip 18.1 from /usr/lib/python3/dist-packages/pip (python 3.7)

pi@pi:~/HAT/pi-overwatch $ python3 -m pip install --user --upgrade pip

pi@pi:~/HAT/pi-overwatch $ python3 -m pip --version
pip 21.3 from /home/pi/.local/lib/python3.7/site-packages/pip (python 3.7)

pi@pi:~/HAT/pi-overwatch $ python3 -m pip install --user --upgrade virtualenv

pi@pi:~/HAT/pi-overwatch $ python3 -m virtualenv --version
virtualenv 20.8.1 from /home/pi/.local/lib/python3.7/site-packages/virtualenv/__init__.py
```
Create the virtual environment and activate
```
pi@pi:~/HAT/pi-overwatch $ python3 -m virtualenv env

pi@pi:~/HAT/pi-overwatch $ source env/bin/activate

(env) pi@pi:~/HAT/pi-overwatch $ which python
/home/pi/HAT/pi-overwatch/venv/bin/python

(env) pi@pi:~/HAT/pi-overwatch $ python --version
Python 3.7.3
```

Now we install/upgrade the requirements

```
(env) pi@pi:~/HAT/pi-overwatch $ pip install wheel

(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install librrd-dev

(env) pi@pi:~/HAT/pi-overwatch $ pip install rrdtool

(env) pi@pi:~/HAT/pi-overwatch $ pip install psutil

# Only if you plan to use a BME280 Temperature/Humidity/Pressure sensor
(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-bme280

# Only if you plan to use a SSD1306 OLED display
(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-ssd1306
(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install libjpeg-dev
(env) pi@pi:~/HAT/pi-overwatch $ pip install image
```

Copy the `default-settings.py` file to `settings.py` and edit as required.
- See the comments in the file
- The default configuration is sufficient for testing, but screens, sensors and GPIO settings need to be enabled in the settings, and some other parameters for the web server and display can be set there too.

Then run with:

```(env) pi@pi:~/HAT/pi-overwatch $ python OverWatch.py```

Note; you can leave the virtualenv using `$ deactivate`

Running as a service to be sorted and documented later
