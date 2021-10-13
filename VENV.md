# Installing in virtualenv
* https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/

### Setup

Start by making sure that you are running a fully updated Raspian install (Buster as of this time of writing), have python3 installed, and have cloned the repo to `/~/HAT/pi-overwatch` eg:

```console
pi@pi:~$ sudo apt install python3 python3-pip
pi@pi:~$ mkdir ~/HAT
pi@pi:~$ git clone https://github.com/easytarget/pi-overwatch.git ~/HAT/pi-overwatch
; Alternatively, if you do not use git and have downloaded a zip or tarball, you should unpack it to: ~/HAT/pi-overwatch
pi@pi:~$ cd ~/HAT/pi-overwatch
```

### Install and Upgrade Requirements

In the cloned repo upgrade our local (user) modules of `pip` and `virtualenv`
```console
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

Create the virtual environment and activate it
- The virtual environment will be located at `/home/pi/HAT/pi-overwatch/env`
- TL;DR: (Quick primer for the unitiated and curious):
  - A python virtual environment is, simply put, a complete and self-contained copy of python and all it's utilities, libraries, and packages.
  - It is installed into a folder (which you specify when creating it) 
  - *Everything* is located in that folder, nothing gets installed to the machines OS, and you can do this as an ordinary user without needing root privileges.
  - This means that your virtualenv can have, say, a different version of python in it than the main 'os' version, either higher or lower, most useful when the OS python version is lagging behind the version you want to use.
  - You can also install python modules into the virtual environment directly, this allows you to use modules and module versions that are different or unsupported on your main OS
  - [This Video](https://www.youtube.com/watch?v=N5vscPTWKOk) and [This](https://www.youtube.com/watch?v=4jt9JPoIDpY) explain it quite well.

```console
pi@pi:~/HAT/pi-overwatch $ python3 -m virtualenv env

pi@pi:~/HAT/pi-overwatch $ source env/bin/activate

(env) pi@pi:~/HAT/pi-overwatch $ which python
/home/pi/HAT/pi-overwatch/env/bin/python

(env) pi@pi:~/HAT/pi-overwatch $ python --version
Python 3.7.3
```

Now we install/upgrade the requirements
- Note that some of these also require you to `apt install` corresponding system libraries that are used by the python module

```console
(env) pi@pi:~/HAT/pi-overwatch $ pip install wheel

(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install librrd-dev

(env) pi@pi:~/HAT/pi-overwatch $ pip install rrdtool

(env) pi@pi:~/HAT/pi-overwatch $ pip install psutil

; Only if you plan to use a BME280 Temperature/Humidity/Pressure sensor:
(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-bme280

; Only if you plan to use a SSD1306 OLED display:
(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-ssd1306
(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install libjpeg-dev
(env) pi@pi:~/HAT/pi-overwatch $ pip install image
```

Copy the `default-settings.py` file to `settings.py` and edit as required.
- See the comments in the file
- The default configuration is sufficient for testing, but screens, sensors and GPIO settings need to be enabled in the settings, and some other parameters for the web server and display can be set there too.

Then test run with:

```console
(env) pi@pi:~/HAT/pi-overwatch $ python OverWatch.py
```

Note; you can leave the virtualenv using `$ deactivate`

Running as a service to be sorted and documented later
