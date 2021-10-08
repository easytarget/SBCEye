# Installing in virtualenv
* https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/
### log

In the cloned repo
```
$ python3 -m pip --version
pip 18.1 from /usr/lib/python3/dist-packages/pip (python 3.7)

$ python3 -m pip install --user --upgrade pip

$ python3 -m pip --version
pip 21.2.4 from /home/pi/.local/lib/python3.7/site-packages/pip (python 3.7)

$ python3 -m pip install --user virtualenv
```
Create the venv and activate
```
pi@pi:~/HAT/pi-overwatch $ python3 -m venv env

pi@pi:~/HAT/pi-overwatch $ source env/bin/activate

(env) pi@pi:~/HAT/pi-overwatch $ which python
/home/pi/HAT/pi-overwatch/env/bin/python
```
Now the requirements
```
(env) pi@pi:~/HAT/pi-overwatch $ pip install wheel

(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-ssd1306

(env) pi@pi:~/HAT/pi-overwatch $ pip install adafruit-circuitpython-bme280

(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install librrd-dev

(env) pi@pi:~/HAT/pi-overwatch $ pip install rrdtool

(env) pi@pi:~/HAT/pi-overwatch $ pip install psutil

(env) pi@pi:~/HAT/pi-overwatch $ sudo apt install libjpeg-dev

(env) pi@pi:~/HAT/pi-overwatch $ pip install image
```
Then run with:
`(env) pi@pi:~/HAT/pi-overwatch $ python OverWatch.py`

Running as a service to be sorted and documented later
