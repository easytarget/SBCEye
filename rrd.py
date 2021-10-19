#import time
import tempfile
import datetime
from pathlib import Path
import rrdtool

class Robin:
    def __init__(self, s, have_sensor, pin_map):
        self.have_sensor = have_sensor
        self.pin_map = pin_map
        self.server_name = s.server_name
        self.wide = s.graph_wide
        self.high = s.graph_high
        self.style = [s.graph_line]
        if s.graph_area:
            self.style.insert(0, s.graph_area)
        if s.graph_comment:
            self.style.append("COMMENT:" + s.graph_comment)
        self.env_db = Path(s.rrd_file_store + "/" + "env.rrd").resolve()
        self.sys_db = Path(s.rrd_file_store + "/" + "sys.rrd").resolve()
        self.pin_db = []
        for pin in range(len(self.pin_map)):
            self.pin_db.append(Path(s.rrd_file_store + "/" + self.pin_map[pin][0] + ".rrd").resolve())
        # Main RRDtool databases
        # One DB file with three data sources for the environmental data
        if self.have_sensor:
            if not self.env_db.is_file():
                print("Generating " + str(self.env_db))
                rrdtool.create(
                    str(self.env_db),
                    "--start", "now",
                    "--step", "60",
                    "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                    "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                    "DS:env-temp:GAUGE:60:U:U",
                    "DS:env-humi:GAUGE:60:U:U",
                    "DS:env-pres:GAUGE:60:U:U")
            else:
                print("Using existing: " + str(self.env_db))

        # One DB file with three data sources for the system data
        if not self.sys_db.is_file():
            print("Generating " + str(self.sys_db))
            rrdtool.create(
                str(self.sys_db),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                "DS:sys-temp:GAUGE:60:U:U",
                "DS:sys-load:GAUGE:60:U:U",
                "DS:sys-mem:GAUGE:60:U:U")
        else:
            print("Using existing: " + str(self.sys_db))
        # One database file for each GPIO line
        for pin in range(len(self.pin_map)):
            if not self.pin_db[pin].is_file():
                print("Generating " + str(self.pin_db[pin]))
                rrdtool.create(
                    str(self.pin_db[pin]),
                    "--start", "now",
                    "--step", "60",
                    "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                    "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                    "DS:status:GAUGE:60:0:1")
            else:
                print("Using existing: " + str(self.pin_db[pin]))

    def update(self, env, sys, states):
        # Update the database with the latest readings
        if self.have_sensor:
            update_cmd = "N:" + str(env["temperature"]) + ":" + str(env["humidity"]) + ":" + str(env["pressure"])
            rrdtool.update(str(self.env_db), update_cmd)
        update_cmd = "N:" + str(sys["temperature"]) + ":" + str(sys["load"]) + ":" + str(sys["memory"])
        rrdtool.update(str(self.sys_db), update_cmd)
        for pin in range(len(self.pin_map)):
            update_cmd = "N:" + str(states[pin])
            rrdtool.update(str(self.pin_db[pin]), update_cmd)

    def draw_graph(self, period, graph):
        # RRD graph generation
        # Returns the generated file for sending in the http response
        start = 'end-' + period
        temp_file = tempfile.NamedTemporaryFile(mode='rb', dir='/tmp', prefix='overwatch_graph')
        timestamp = datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y")
        if graph == "env-temp":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "Environment Temperature: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "50",
                        "--lower-limit", "10",
                        "--left-axis-format", "%3.1lf\u00B0C",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.env_db) + ":env-temp:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        elif graph == "env-humi":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "Environment Humidity: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "100",
                        "--lower-limit", "0",
                        "--left-axis-format", "%3.0lf%%",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.env_db) + ":env-humi:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        elif graph == "env-pres":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "Environment Pressure: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "1040",
                        "--lower-limit", "970",
                        "--units-exponent", "0",
                        "--left-axis-format", "%4.0lfmb",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.env_db) + ":env-pres:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        elif graph == "sys-temp":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "CPU Temperature: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "80",
                        "--lower-limit", "40",
                        "--left-axis-format", "%3.1lf\u00B0C",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.sys_db) + ":sys-temp:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        elif graph == "sys-load":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "CPU Load Average: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "3",
                        "--lower-limit", "0",
                        "--units-exponent", "0",
                        "--left-axis-format", "%2.3lf",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.sys_db) + ":sys-load:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        elif graph == "sys-mem":
            try:
                rrdtool.graph(
                        temp_file.name,
                        "--title", "System Memory Use: last " + period,
                        "--width", str(self.wide),
                        "--height", str(self.high),
                        "--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--upper-limit", "100",
                        "--lower-limit", "0",
                        "--left-axis-format", "%3.0lf%%",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "DEF:data=" + str(self.sys_db) + ":sys-mem:AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        else:
            for pin in range(len(self.pin_map)):
                if graph == "pin-" + self.pin_map[pin][0]:
                    try:
                        rrdtool.graph(
                                temp_file.name,
                                "--title", self.pin_map[pin][0] + " Pin State: last " + period,
                                "--width", str(self.wide),
                                "--height", str(self.high/2),
                                "--full-size-mode",
                                "--start", start,
                                "--end", "now",
                                "--upper-limit", "1.1",
                                "--lower-limit", "-0.1",
                                "--left-axis-format", "%3.1lf",
                                "--watermark", self.server_name + " :: " + timestamp,
                                "DEF:data=" + str(self.pin_db[pin]) + ":status:AVERAGE",
                                *self.style)
                    except Exception as rrd_error:
                        print(rrd_error)
        response = temp_file.read()
        if len(response) == 0:
            print("Error: png file generation failed for : " + graph + " : " + period)
        temp_file.close()
        return response
