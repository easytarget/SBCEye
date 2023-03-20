# A brief guide to the architecture of this tool and how to contribute
I created the SBCEye to monitor a RaspberryPI that sits in my workshop and runs a couple of 3D printers, a couple of USB webcams, a wireless access point (hostapd) and also controls some GPIO relays for a lamp and the 3D printer power. 
- This machine also has a small OLED display, a BME280 environmental sensor and a button on a space GPIO pin mounted on a HAT that also provides adequate power.
- SBCEye, as it stands, reflects my needs for this machine. But has core functionality suitable for many Small Systems sitting in corners doing routine tasks.

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
    - The display can be configured with a 'screensaver' to blank or invert it in order to reduce oled burn-in issues
- Housekeeping:
  - SBCEye uses nice() to run with reduced priority, and does not need root access
  - An internal cache is used to reduce RRDB disk writes (important on machines running from SD Cards)
    - The cache is written into the database once its contents exceed five minutes of data, by default
    - Requesting graphs causes an immediate cache write since the RRD graph tool works from the database
    - The cache is also written when the program exits or restarts 
  - The RRDB database is backupd up and rotated on a configurable schedule
  - The RRDB database can be dumped out (as gzipped xml) via the web UI
  - The logs will roll over and be truncated on a configurable schedule
  - Threading is used for HTTP requests, graph generation and ping tests
  - The display (if configured) runs in a seperate process
- Button:
  - My 'Special needs' feature, I have a Illumination lamp for my webcams etc. which is controled via a GPIO pin and relay, I want/need a physical switch for this in the workshop, so I added the ability to let me control the lamp via a physical button, and also via the Web interface.
  - This is a seperate function, detached from the main data gathering loops and config
- Pain:
  - RRDTool's python C bindings dont play well with stdout/error, so we need to run the commandline tool for graphs and dumps 👎

## Data Driven (sort of)
We gather data (as floating point numbers) from a variety of sources and store it in a dictionary as a `key:value` pair.
- The python scheduler runs regular tasks to gather, store and log the data
- The http server runs on request and processes the data to generate the UI
- Other schedules handle backing up the database and 'heartbeat' logs
- When data entries change they are sent via a queue to the display process, which itself uses a schedule to drive animation and the screensaver
- Once initialised the main loop of this program simply services the wscheduler and nothing else
