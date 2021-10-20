import tempfile
import datetime
from pathlib import Path
import rrdtool

class Robin:
    def __init__(self, s, env, sys, pins):
        self.env = env
        self.sys = sys
        self.pins = pins
        self.pin_map = s.pin_map
        self.server_name = s.server_name
        self.wide = s.graph_wide
        self.high = s.graph_high
        self.style = [s.graph_line]
        if s.graph_area:
            self.style.insert(0, s.graph_area)
        if s.graph_comment:
            self.style.append("COMMENT:" + s.graph_comment)

        # DataBase

        # Calculate desired data sources (things we will record)
        if env:
            sources = ['env-temp','env-humi','env-pres']
        else:
            sources = []
        sources.extend(['sys-temp','sys-load','sys-mem'])
        for _, pin in enumerate(self.pin_map):
            sources.append('pin-' + pin[0].lower())
        print(f"We require:  {sources}")

        # File, create new if necesscary
        self.db = Path(s.rrd_file_path + '/' + s.rrd_file_name).resolve()
        print(f"RRD DB file: {self.db}")
        if not self.db.is_file():
            print("Generating " + str(self.db))
            ds_list = []
            for ds_entry in sources:
                ds_list.append("DS:" + ds_entry + ":GAUGE:60:U:U")
            rrdtool.create(
                str(self.db),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                *ds_list)
        else:
            print("Using existing: " + str(self.db))

        # get a list of existing data sources in the database
        existing_sources = []
        for key in rrdtool.info(str(self.db)):
            if key[:2] == 'ds' and key[-6:] == '.index':
                existing_sources.append(key[3:-7])
        print(f"DB file has: {existing_sources}")

        # generate the update template and create any missing data sources in db file
        ds_template = ""
        for ds_entry in sources:
            ds_template += ':' + str(ds_entry)
            if not ds_entry in existing_sources:
                print(f"Adding: {ds_entry} to {self.db}")
                rrdtool.tune(
                    str(self.db),
                    "DS:" + ds_entry + ":GAUGE:60:U:U")
        self.update_template = ds_template[1:]
        print(f"DB update template: {self.update_template}")

        print("------------ OLD DB STUFF --------------")

        self.env_db = Path(s.rrd_file_store + "/" + "env.rrd").resolve()
        self.sys_db = Path(s.rrd_file_store + "/" + "sys.rrd").resolve()
        self.pin_db = []
        for pin in range(len(self.pin_map)):
            self.pin_db.append(Path(s.rrd_file_store + "/" + self.pin_map[pin][0] + ".rrd").resolve())

        # Main RRDtool databases
        # One DB file with three data sources for the environmental data
        if self.env:
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

    def update(self):
        # Update the database with the latest readings
        dataline = "N:"
        if self.env:
            update_cmd = str(self.env["temperature"]) + ":" + str(self.env["humidity"]) + ":" + str(self.env["pressure"])
            rrdtool.update(str(self.env_db), "N:" + update_cmd)
            dataline += update_cmd
        update_cmd = str(self.sys["temperature"]) + ":" + str(self.sys["load"]) + ":" + str(self.sys["memory"])
        dataline += ':' + update_cmd
        rrdtool.update(str(self.sys_db), "N:" + update_cmd)
        for idx, pin in enumerate(self.pins):
            update_cmd = str(pin)
            rrdtool.update(str(self.pin_db[idx]), "N:" + update_cmd)
            dataline += ':' + update_cmd
        print(f"{dataline}")
        rrdtool.updatev(
                str(self.db),
                "--template", self.update_template,
                dataline)

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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
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
                        "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
                        *self.style)
            except Exception as rrd_error:
                print(rrd_error)
        else:
            for idx, pin in enumerate(self.pin_map):
                if graph == "pin-" + pin[0]:
                    try:
                        rrdtool.graph(
                                temp_file.name,
                                "--title", pin[0] + " Pin State: last " + period,
                                "--width", str(self.wide),
                                "--height", str(self.high/2),
                                "--full-size-mode",
                                "--start", start,
                                "--end", "now",
                                "--upper-limit", "1.1",
                                "--lower-limit", "-0.1",
                                "--left-axis-format", "%3.1lf",
                                "--watermark", self.server_name + " :: " + timestamp,
                                "DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
                                *self.style)
                    except Exception as rrd_error:
                        print(rrd_error)
        response = temp_file.read()
        if len(response) == 0:
            print("Error: png file generation failed for : " + graph + " : " + period)
        temp_file.close()
        return response
