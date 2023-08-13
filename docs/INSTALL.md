# Installing in virtualenv
* https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/

## Supporteed install method

The install steps below will set SBCEye up using a separate user in a virtual environment, and start it automatically via a system service. This provides some security and isolation but SBCEye is still not suitable for running on a public IP address. If you are familiar with Python then feel free to improvise on these instructions, but I wont be very helpful if it all goes wrong.

### Setup

Start by making sure that you are running a fully updated OS install, have git, python3, python3-pip and python3-dev and lm-sensors installed, have created an 'eye' user and have cloned the repo to `~eye/SBCEye` eg:

```console
; Install python and dependencies
admin@sbc:~$ sudo apt update
admin@sbc:~$ sudo apt install python3 python3-dev python3-pip git rrdtool librrd-dev lm-sensors

; Only if you plan to use a SSD1306 OLED display:
admin@sbc:~$ sudo apt install libjpeg-dev libopenjp2-7-dev libtiff-dev fonts-liberation

admin@sbc:~$ sudo useradd -m eye

; If using either a screen, BME sensor or GPIO pin monitoring you must make sure the eye user is in the gpio group:
admin@sbc:~$ sudo usermod -a -G gpio eye

; Become the 'eye' user
admin@sbc:~$ sudo su - eye

; Clone the repo
eye@sbc:~$ git clone https://github.com/easytarget/SBCEye.git ~/SBCEye
; Alternatively, if you do not use git and have downloaded a zip or tarball, you should unpack it to: ~/SBCEye

eye@sbc:~$ cd ~/SBCEye
```

### Install and Upgrade Requirements

In the cloned repo upgrade our local (user) modules of `pip` and `virtualenv`
```console
eye@sbc:~/SBCEye $ pwd
/home/eye/SBCEye
eye@sbc:~/SBCEye $ python3 -m pip install --user --upgrade pip
eye@sbc:~/SBCEye $ python3 -m pip install --user --upgrade virtualenv
```

Create the virtual environment and activate it
- The virtual environment will be located at `/home/eye/SBCEye/env`
- TL;DR: (Quick primer about Python Virtual Environments, if needed):
  - A python virtual environment is, simply put, a complete and self-contained copy of python and all it's utilities, libraries, and packages.
  - It is installed into a folder (which you specify when creating it)
  - *Everything* is located in that folder, *nothing* gets installed to the machines OS, which means you can do this as an ordinary user without needing root privileges.
  - The end result is, essentially, a form of containerization. Your virtualenv can have a different version of python in it than the main 'os' version, either higher or lower. This is useful when the OS default Python version is lagging behind the version you want to use.
  - You install python modules into the virtual environment directly, superseding the system and user package installs. This allows you to use modules and module versions that are different or unsupported on your main OS
  - [This Video](https://www.youtube.com/watch?v=N5vscPTWKOk) and [This](https://www.youtube.com/watch?v=4jt9JPoIDpY) explain it quite well.

```console
eye@sbc:~/SBCEye $ python3 -m virtualenv env

eye@sbc:~/SBCEye $ source env/bin/activate

(env) eye@sbc:~/SBCEye $ which python
/home/eye/SBCEye/env/bin/python
```

Now we install/upgrade the requirements
- note there are some `apt install` commands to be run as root here too... I'll split them into the 'root prep' section, with distro-specific notes in the future.
```console
(env) eye@sbc:~/SBCEye $ pip install --upgrade pip
(env) eye@sbc:~/SBCEye $ pip install --upgrade wheel

(env) eye@sbc:~/SBCEye $ pip install psutil schedule setproctitle rrdtool

; If you wish to control a gpio pin via a button or url you need to install RPi.GPIO
; - this is not necesscary if you just want to monitor (not control) pins.
; RPi.GPIO is (currently, november'21) broken on BULLSEYE unless you use a pre-release. sigh. 
(env) eye@sbc:~/SBCEye $ pip install RPi.GPIO==0.7.1a4

; Only if you plan to use a BME280 Temperature/Humidity/Pressure sensor:
(env) eye@sbc:~/SBCEye $ pip install adafruit-circuitpython-bme280

; Only if you plan to use a SSD1306 OLED display:
(env) eye@sbc:~/SBCEye $ pip install adafruit-circuitpython-ssd1306 image
```

Copy the `defaults.ini` file to `config.ini` and edit as required.
- See the comments in the file
- The default configuration is sufficient for testing, but screens, sensors and GPIO settings need to be enabled in the settings
- Some other parameters for the web server, logging and display can be set there too
```

Then test run with:

```console
(env) eye@sbc:~/SBCEye $ python SBCEye.py
```
The file `SBCEye.log` should be created in the SBCEye directory, and contain a startup log

Debug messages, errors, etc are printed to the console

The web server should be available on `http://<machines-address>:7080/` (or whatever is configured in the settings)

Note; If you want to leave the virtualenv at any time you can do so with `$ deactivate`, if you want to delete the virtualenv it is as simple as deleting the 'env' folder and all it's sub-folders.

## Set up as a service

Once you have everything installed, configured and tested by running on the console you should start running this as a system service. The SBCEye will then run automatically at boot and operate in the background like other services.

```console
admin@sbc:~ $ cd ~eye/SPBEye
admin@sbc:/home/eye/SBCEye $ sudo ln -s /home/eye/SBCEye/SBCEye.service /etc/systemd/system/
admin@sbc:/home/eye/SBCEye $ sudo systemctl daemon-reload
admin@sbc:/home/eye/SBCEye $ sudo systemctl enable --now SBCEye.service

admin@sbc:/home/eye/SBCEye $ sudo systemctl status SBCEye.service
● SBCEye.service - SBCEye monitoring for SBCs
   Loaded: loaded (/etc/systemd/system/SBCEye.service; enabled; vendor preset: enabled)
   Active: active (running) since Wed 2021-10-13 19:37:49 CEST; 10min ago
 Main PID: 20376 (python)
    Tasks: 2 (limit: 4164)
   CGroup: /system.slice/SBCEye.service
           └─20376 /home/eye/SBCEye/env/bin/python /home/eye/SBCEye/SBCEye.py

Oct 13 19:37:49 pi.easytarget.org systemd[1]: Started SBCEye script for PI Hat.
```

## Upgrading
Quick notes; to be expanded later as required, assumes you use git.
- go to the SBCEye repo
- git pull
- merge any changes from defaults.ini to config.ini
- stop the service
- start the service

Pip packages should not need upgrading any time soon if everything is working properly, but I'll investigate pip freeze and how to do this properly in the future as it becomes necessary.
