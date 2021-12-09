# A brief guide to the architecture of this tool and how to contribute
I created the overwatch to monitor a RaspberryPI that sits in my workshop and runs a couple of 3D printers, a couple of USB webcams, a wireless access point (hostapd) and also controls a big lamp and the 3D printer power via some GPIO relays. 
- This machine also has a small OLED display, a BME280 environmental sensor and a button on a space GPIO pin mounted on a HAT that also provides adequate power.
- Overwatch, as it stands, reflects my needs for this machine. But has core functionality suitable for many PI's sitting in corners doing routine tasks.

## Features
- Gathers Data, every 10 seconds by default:
  - 9 OS readings (cpu, load, io, etc)
  - BME280 temperature, humidity, pressure (if installed and enabled)
  - Ping response status and times (configurable list)
  - GPIO pin status (configurable list, gathered every 2 seconds by default)
- Stores Data:
  - Uses a [Round Robin Database](https://en.wikipedia.org/wiki/RRDtool) to store the readings in three resolutions:
    - every 10 seconds for 3 weeks
    - every minute for three months
    - every hour for three years
- Reports:
  - Web UI displays current values and status for the data
  - Web UI provides historical graphs of the data
  - A viewable Log notes events for ping and pin state changes
  - If a display is configured the environmental and system info is displayed on that via 'sliding' screens
- Housekeeping:
  - The script runs with reduced priority (nice) and does not need root access
  - The RRDB database is backupd up and rotated on a configurable schedule
  - The RRDB database can be dumped out (as gzipped xml) via the web UI
  - The logs will roll over and be truncated on a configurable schedule
  - The display (if configured) runs in a seperate process
  - Threading is used for HTTP requests, graph generation and ping tests
- Button:
  - My 'Special needs' feature, I have a Illumination lamp for my webcams etc. which is controled via a GPIO pin and relay, I want/need a physical switch for this in the workshop, so I added the ability to let me control the lamp via a physical button, and also via the Web interface.
  - This is a seperate function, detached from the main data gathering loops and config

## Data Driven (sort of)
We gather data (as floating point numbers) from a variety of sources and store it in a dictionary as a `key:value` pair, RRD 

