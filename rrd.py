import tempfile
import datetime
from pathlib import Path
import rrdtool

class Robin:
    def __init__(self, s, env, sys, pin):
        self.env = env
        self.sys = sys
        self.pin = pin
        self.pin_map = s.pin_map
        self.server_name = s.server_name
        self.time_format = s.time_format
        self.wide = s.graph_wide
        self.high = s.graph_high
        self.style = [s.graph_line]
        if s.graph_area:
            self.style.insert(0, s.graph_area)
        if s.graph_comment:
            self.style.append(f'COMMENT: {s.graph_comment}')

        # Data sources, min, max values
        sources = {}
        if len(self.env) > 0:
            sources['env-temp'] = ('-40','80')
            sources['env-humi'] = ('0','100')
            sources['env-pres'] = ('300','1100')
        sources['sys-temp'] = ('-10','110')
        sources['sys-load'] = ('0','10')
        sources['sys-mem']  = ('0','100')
        for _, pin in enumerate(self.pin_map):
            sources['pin-' + pin[0].lower()] = ('0','1')

        # File, create if necesscary
        self.db = Path(s.rrd_file_path + '/' + s.rrd_file_name).resolve()
        if not self.db.is_file():
            print("Generating " + str(self.db))
            ds_list = []
            for ds,(mi,ma) in sources.items():
                ds_list.append(f"DS:{ds}:GAUGE:60:{mi}:{ma}")
            rrdtool.create(
                str(self.db),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",  # 3 years per hour
                *ds_list)
            print(f'''rrdtool.create(
                str({self.db}),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",  # 3 years per hour
                {ds_list})''')
        else:
            print("Using existing: " + str(self.db))

        # get a list of existing data sources in the database
        existing_sources = []
        for key in rrdtool.info(str(self.db)):
            if key[:2] == 'ds' and key[-6:] == '.index':
                existing_sources.append(key[3:-7])

        # generate the update template and create any missing data sources in db file
        ds_template = ""
        for ds,(mi,ma) in sources.items():
            ds_template += ':' + str(ds)
            if not ds in existing_sources:
                print(f"Adding: {ds} to {self.db}")
                rrdtool.tune(
                    str(self.db),
                    f"DS:{ds}:GAUGE:60:{mi}:{ma}")
        self.update_template = ds_template[1:]

    def update(self):
        # Update the database with the latest readings
        dataline = "N"
        if len(self.env) > 0:
            dataline += ':' + str(self.env["temperature"]) + ":" + str(self.env["humidity"]) + ":" + str(self.env["pressure"])
        dataline += ':' + str(self.sys["temperature"]) + ":" + str(self.sys["load"]) + ":" + str(self.sys["memory"])
        for idx, pin in enumerate(self.pin):
            dataline += ':' + str(pin)
        rrdtool.update(
                str(self.db),
                "--template", self.update_template,
                dataline)

    def draw_graph(self, period, graph):
        # RRD graph generation
        # Returns the generated file for sending in the http response
        graphArgMap = {
                'env-temp': ('Environment Temperature','50','10','%3.1lf\u00B0C'),
                'env-humi': ('Environment Humidity','100','0','%3.0lf%%'),
                'env-pres': ('Environment Pressure','1040','970','%4.0lfmb','0'),
                'sys-temp': ('CPU Temperature','80','40','%3.1lf\u00B0C'),
                'sys-load': ('CPU Load Average','3','0','%2.3lf','0'),
                'sys-mem':  ('System Memory Use','100','0','%3.0lf%%')
                }
        for _, pin in enumerate(self.pin_map):
            graphArgMap["pin-" + pin[0]] = (pin[0] + ' Pin State','1.1','-0.1','%3.1lf')

        if graph in graphArgMap:
            temp_file = tempfile.NamedTemporaryFile(mode='rb', dir='/tmp', prefix='overwatch_graph')
            start = 'end-' + period
            timestamp = datetime.datetime.now().strftime(self.time_format)
            rrd_args = ["--full-size-mode",
                        "--start", start,
                        "--end", "now",
                        "--watermark", self.server_name + " :: " + timestamp,
                        "--width", str(self.wide)]
            if graph[:4] == 'pin-':
                rrd_args.extend(["--height", str(self.high/2)])
            else:
                rrd_args.extend(["--height", str(self.high)])
            rrd_args.extend(["--title", graphArgMap[graph][0] + ": last " + period,
                             "--upper-limit", graphArgMap[graph][1],
                             "--lower-limit", graphArgMap[graph][2],
                             "--left-axis-format", graphArgMap[graph][3]])
            if len(graphArgMap[graph]) > 4:
                rrd_args.extend(["--units-exponent", graphArgMap[graph][4]])
            rrd_args.extend(["DEF:data=" + str(self.db) + ":" + graph.lower() + ":AVERAGE",
                             *self.style])
            try:
                rrdtool.graph(
                        temp_file.name,
                        *rrd_args)
            except Exception as rrd_error:
                print(rrd_error)
            response = temp_file.read()
            if len(response) == 0:
                print("Error: png file generation failed for : " + graph + " : " + period)
            temp_file.close()
        else:
            response = bytearray()
            print("Error: No graph map entry for type: " + graph)
        return response
