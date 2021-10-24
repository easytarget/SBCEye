import tempfile
import datetime
from pathlib import Path
import rrdtool

class Robin:
    def __init__(self, s):
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

        # Sensor and system sources with limits (min,max)
        self.DATA_SOURCES = {
                'env-temp': ('-40','80'),
                'env-humi': ('0','100'),
                'env-pres': ('300','1100'),
                'sys-temp': ('-10','110'),
                'sys-load': ('0','10'),
                'sys-mem': ('0','100'),
            }

        # Graphs and parameters
        self.GRAPH_MAP = {
                'env-temp': ('Environment Temperature','50','10','%3.1lf\u00B0C'),
                'env-humi': ('Environment Humidity','100','0','%3.0lf%%'),
                'env-pres': ('Environment Pressure','1040','970','%4.0lfmb','0'),
                'sys-temp': ('CPU Temperature','80','40','%3.1lf\u00B0C'),
                'sys-load': ('CPU Load Average','3','0','%2.3lf','0'),
                'sys-mem':  ('System Memory Use','100','0','%3.0lf%%')
                }
        # pins
        for name, _ in self.pin_map:
            self.DATA_SOURCES[f'pin-{name}'] = ('0','1')
            self.GRAPH_MAP[f'pin-{name}'] = f'{name} Pin State','1.1','-0.1','%3.1lf'

        # Database File
        self.db = Path(s.rrd_file_dir + '/' + s.rrd_file_name).resolve()
        if not self.db.is_file():
            # Generate a new file when none present
            print(f'Generating {str(self.db)}')
            ds_list = []
            for ds,(mi,ma) in self.DATA_SOURCES.items():
                ds_list.append(f"DS:{ds}:GAUGE:60:{mi}:{ma}")
            rrdtool.create(
                str(self.db),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",  # 3 years per hour
                *ds_list)
        else:
            print("Using existing: " + str(self.db))

        # get a list of existing data sources in the database
        existing_sources = []
        for key in rrdtool.info(str(self.db)):
            if key[:2] == 'ds' and key[-6:] == '.index':
                existing_sources.append(key[3:-7])

        # create any missing data sources in the database
        for ds,(mi,ma) in self.DATA_SOURCES.items():
            if not ds in existing_sources:
                print(f"Adding: {ds} to {self.db}")
                rrdtool.tune(
                    str(self.db),
                    f"DS:{ds}:GAUGE:60:{mi}:{ma}")


    def update(self,data):
        # Update the database with the latest readings
        template = ''
        dataline = 'N'
        for source in self.DATA_SOURCES.keys():
            template += f':{source}'
            dataline += f':{data[source]}'
        template = template.lstrip(':')
        rrdtool.update(
                str(self.db),
                "--template", template,
                dataline)

    def draw_graph(self, period, graph):
        # RRD graph generation
        # Returns the generated file for sending as the http response
        if graph in self.GRAPH_MAP.keys():
            params = self.GRAPH_MAP[graph]
            print(params)
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
            rrd_args.extend(["--title", params[0] + ": last " + period,
                             "--upper-limit", params[1],
                             "--lower-limit", params[2],
                             "--left-axis-format", params[3]])
            if len(params) > 4:
                rrd_args.extend(["--units-exponent", params[4]])
            rrd_args.extend([f'DEF:data={str(self.db)}:{graph}:AVERAGE',
                             *self.style])
            try:
                rrdtool.graph(
                        temp_file.name,
                        *rrd_args)
            except Exception as rrd_error:
                print(rrd_error)
            response = temp_file.read()
            if len(response) == 0:
                print(f'Error: png file generation failed for : {graph} : {period}')
            temp_file.close()
        else:
            response = bytearray()
            print(f'Error: No graph map entry for type: {graph}')
        return response
