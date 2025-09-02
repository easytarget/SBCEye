# Host system requirements
The core features of SBCEye (cpu/memory/disk/connectivity monitoring) should run on any *modern* **Linux** platform, I have tested it on Pi3 and Pi4 devices, plus my VisionFive2 (risc-v), mq-pro (single core and slow risc-v). It also runs fine on a fedora based laptop, but is really optimised for SBC's, not workstations.

The GPIO features use standard Linux libraries. But you will need to ensure GPIO and I2C pins are available on your platform (this is done via the device tree and device tree overlays):
- PI: <------------ show howto in rpi-config
- VF2: <----------- maybe example with DTO's

# Python
This guide uses a Python virtual environment for the install, your host system needs Python 3.9 (or later) and the venv module, these should be installed by default on most systems, or available in the repositories for you distribution.
* https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/

## Install Guide:

The install steps below will set SBCEye up using a separate user in a virtual environment, and start it automatically via a system service. This provides some security and isolation but SBCEye is still not suitable for running on a public IP address. If you are familiar with Python then feel free to improvise on these instructions, but I wont be very helpful if it all goes wrong.

### Setup

Start by making sure that you are running a fully updated OS install, have git, python3, python3-pip and python3-dev and lm-sensors installed, have created an 'eye' user and have cloned the repo to `~eye/SBCEye` eg:

```console
# Install python and dependencies 
admin@sbc:~$ sudo apt update
admin@sbc:~$ sudo apt install python3 python3-dev python3-pip git rrdtool librrd-dev lm-sensors
;or (RHEL) : sudo dnf install python3 python3-devel python3-pip git rrdtool lm_sensors rrdtool-devel

# If you want to monitor GPIO pins
admin@sbc:~$ sudo apt install gpiod
;or (RHEL) : sudo dnf install TODO

# If you plan to use a I2C SSD1306 OLED display or BME280 environmental sensor
admin@sbc:~$ sudo apt install i2c-tools
;or (RHEL) : sudo dnf install TODO

# If you installed either `i2c-tools` or `gpiod` above I suggest rebooting
#  at this point to ensure the services are running.

# Only if you plan to use a screen :
admin@sbc:~$ sudo apt install fonts-liberation
;or (RHEL) : sudo dnf install TODO

# Create a dedicate user account (and set bash as our shell)
admin@sbc:~$ sudo useradd -m eye
admin@sbc:~$ sudo usermod -s /bin/bash eye

# If using GPIO pin monitoring the eye user needs to be in the `gpio` group:
admin@sbc:~$ sudo usermod -a -G gpio eye

# If using a I2C screen or BME280 sensor the eye user needs to be in the `i2c` group:
admin@sbc:~$ sudo usermod -a -G i2c eye

# Become the 'eye' user
admin@sbc:~$ sudo su - eye

# Clone the repo
eye@sbc:~$ git clone https://github.com/easytarget/SBCEye.git ~/SBCEye
;alternatively, if you have downloaded a .zip or tarball, unpack it to: ~/SBCEye

eye@sbc:~$ cd ~/SBCEye
```

### Install and Upgrade Requirements

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
# create the venv
eye@sbc:~/SBCEye $ python3 -m venv env

# activate it (can also do: 'source env/bin/activate') 
eye@sbc:~/SBCEye $ . env/bin/activate

# verify we are now using python from the environment
(env) eye@sbc:~/SBCEye $ which python
/home/eye/SBCEye/env/bin/python
(env) eye@sbc:~/SBCEye $ python --version
Python 3.11.2
```

Now we install/upgrade the requirements into the virtual environment
```console
# make sure our tooling is up-to-date
(env) eye@sbc:~/SBCEye $ pip install --upgrade pip
(env) eye@sbc:~/SBCEye $ pip install --upgrade wheel

# Core libraries needed for all installs
(env) eye@sbc:~/SBCEye $ pip install psutil schedule setproctitle rrdtool-bindings

# If you want to monitor GPIO pins:
(env) eye@sbc:~/SBCEye $ pip install gpiod

# If you have either a screen or sensor:
(env) eye@sbc:~/SBCEye $ pip install smbus2

# Only if you plan to use a BME280 Temperature/Humidity/Pressure sensor:
(env) eye@sbc:~/SBCEye $ pip install pimoroni_bme280

# Only if you plan to use a SSD1306 OLED display:
(env) eye@sbc:~/SBCEye $ pip install luma.core luma.oled
;This will take time since PIP needs to build (compile) wheels for some of the dependencies.
```

Copy the `defaults.ini` file to `config.ini` and edit as required.
- See the comments in the file
- The default configuration is sufficient for testing, but screens, sensors and GPIO settings need to be enabled in the settings
- Some other parameters for the web server, logging and display can be set there too

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
admin@sbc:~ $ cd ~eye/SBCEye
admin@sbc:/home/eye/SBCEye $ sudo ln -s /home/eye/SBCEye/SBCEye.service /etc/systemd/system/
admin@sbc:/home/eye/SBCEye $ sudo systemctl daemon-reload
admin@sbc:/home/eye/SBCEye $ sudo systemctl enable --now SBCEye.service

admin@sbc:/home/eye/SBCEye $ sudo systemctl status SBCEye.service
● SBCEye.service - SBCEye monitoring script
     Loaded: loaded (/etc/systemd/system/SBCEye.service; enabled; preset: enabled)
     Active: active (running) since Tue 2025-08-26 13:37:12 CEST; 2s ago
   Main PID: 494328 (SBCEye: worksho)
      Tasks: 8 (limit: 760)
        CPU: 1.204s
     CGroup: /system.slice/SBCEye.service
             ├─494328 "SBCEye: workshop.pi3b"
             └─494334 "SBCEye screen: workshop.pi3b"

; Note; The example above has a screen configured, and the screen process is shown running seperately (but in the same CGroup).
```

## Upgrading
Quick notes; to be expanded later as required, assumes you use git.
- go to the SBCEye repo
- git pull
- merge any changes from defaults.ini to config.ini
- stop the service
- start the service

Pip packages should not need upgrading any time soon if everything is working properly, but I'll investigate pip freeze and how to do this properly in the future as it becomes necessary.
