import os
import tempfile
import time
from pathlib import Path
import logging
import gzip
import rrdtool

class Robin:
    def __init__(self, s, data):
        self.graph_args = {}
        self.graph_args['name'] = s.name
        self.graph_args['time_format'] = s.time_format
        self.graph_args['wide'] = s.graph_wide
        self.graph_args['high'] = s.graph_high
        self.graph_args['style'] = [s.graph_line]
        if s.graph_area:
            self.graph_args['style'].insert(0, s.graph_area)
        if s.graph_comment_l:
            self.graph_args['style'].append(f'COMMENT: {s.graph_comment_l}')
        if s.graph_comment_r:
            self.graph_args['style'].append(f'COMMENT: {s.graph_comment_r}')

        # Sensor and system sources with limits (min,max)
        self.data_sources = {
                'env-temp': ('-40','80'),
                'env-humi': ('0','100'),
                'env-pres': ('300','1100'),
                'sys-temp': ('-10','110'),
                'sys-load': ('0','10'),
                'sys-mem': ('0','100'),
            }

        # Graphs and parameters
        self.graph_map = {
                'env-temp': (f'{s.web_sensor_name} Temperature','40','10','%3.1lf\u00B0C',
                    '--alt-autoscale'),
                'env-humi': (f'{s.web_sensor_name} Humidity','100','0','%3.0lf%%'),
                'env-pres': (f'{s.web_sensor_name} Pressure','1100','900','%4.0lfmb',
                    '--alt-autoscale', '--units-exponent','0', '--y-grid','25:1'),
                'sys-temp': ('CPU Temperature','80','40','%3.1lf\u00B0C'),
                'sys-load': ('CPU Load Average','2','0','%2.3lf','--alt-autoscale-max'),
                'sys-mem':  ('System Memory Use','100','0','%3.0lf%%'),
                }
        # pins
        for name in s.pin_map.keys():
            self.data_sources[f'pin-{name}'] = ('0','1')
            self.graph_map[f'pin-{name}'] = (f'{name} Pin State','1','-0.01','%3.1lf',
                    '--alt-autoscale')

        # set the list of active and storable sources
        self.template= ''
        self.sources = []
        for source,_ in self.data_sources.items():
            if source in data.keys():
                self.sources.append(source)
                self.template += f'{source}:'
        print(f'Storable sources = {self.sources}')
        self.template = self.template.rstrip(':')
        print(f'Template = {self.template}')

        # Database File
        self.db_file = Path(f'{s.rrd_dir}/{s.rrd_file_name}').resolve()
        source_file = Path(f'{s.rrd_dir}/{s.rrd_file_name}.old').resolve()
        if not self.db_file.is_file():
            # Generate a new file when none present
            print(f'Generating {str(self.db_file)}')
            ds_list = []
            for source in self.sources:
                mini = self.data_sources[source][0]
                maxi = self.data_sources[source][1]
                ds_list.append(f'DS:{source}:GAUGE:60:{mini}:{maxi}')
                print(f" data source: {source} ({mini},{maxi})")
            args = [str(self.db_file)]
            if source_file.is_file():
                print(f'Importing from previous {source_file}')
                args.append(["--source",str(source_file)])
            args.append(["--start", "now-10s",
                    "--step", "10s",
                    "RRA:AVERAGE:0.5:1:181440",    # 3 weeks per 10s
                    "RRA:AVERAGE:0.5:6:786240",    # 3 months per minute
                    "RRA:AVERAGE:0.5:360:158112"]) # 3 years per hour
            rrdtool.create(*args,*ds_list)
        else:
            print(f'Using existing: {str(self.db_file)}')

        # get a list of existing data sources in the database
        existing_sources = []
        for key in rrdtool.info(str(self.db_file)):
            if key[:2] == 'ds' and key[-6:] == '.index':
                existing_sources.append(key[3:-7])

        # create any missing data sources in the database
        for source in self.sources:
            if not source in existing_sources:
                mini = self.data_sources[source][0]
                maxi = self.data_sources[source][1]
                print(f"Adding: {source} ({mini},{maxi}) to {self.db_file}")
                rrdtool.tune(
                    str(self.db_file),
                    f"DS:{source}:GAUGE:60:{mini}:{maxi}")

        # use a home-brew local cache (list) here, rrdcache does not like templates
        self.cache = []
        self.last_write = 0
        self.cache_age = s.rrd_cache_age
        print('RRD database and cache configured and enabled')
        logging.info(f'RRD database is: {str(self.db_file)}')

    def dump(self):
        ret = ''
        with tempfile.NamedTemporaryFile(mode='rb', dir='/tmp',
                prefix='overwatch_dump') as temp_file:
            rrdtool.dump(str(self.db_file), temp_file.name)
            print(f'Dump is: {os.stat(temp_file.name).st_size} bytes in size')
            ret = gzip.compress(temp_file.read())
            print(f'Dump is: {len(ret)} bytes compressed')
        return ret

    def dump_fail(self):
        import io
        from contextlib import redirect_stdout,redirect_stderr

        f = io.StringIO()
        with redirect_stdout(f):
            rrdtool.dump(str(self.db_file))
        dump = f.getvalue()
        print(f'Dump is: {len(dump)} bytes in size')
        ret = gzip.compress(dump)
        print(f'Dump is: {len(ret)} bytes compressed')
        return ret

    def update(self, data):
        # Update the database with the latest readings
        dataline = str(int(time.time()))
        for source in self.sources:
            dataline += f':{data[source]}'
        if dataline:
            self.cache.append(dataline)
        if time.time() > (self.last_write + self.cache_age):
            self.write_updates()

    def write_updates(self):
        if len(self.cache) > 0:
            rrdtool.update(
                    str(self.db_file),
                    "--template", self.template,
                    *self.cache)
            self.cache = []
        self.last_write = time.time()

    def draw_graph(self, start, end, duration, graph):
        # RRD graph generation
        # Returns the generated file for sending as the http response
        if (graph in self.sources) and (graph in self.graph_map.keys()):
            self.write_updates()
            params = self.graph_map[graph]
            response = bytearray()
            with tempfile.NamedTemporaryFile(mode='rb', dir='/tmp',
                    prefix='overwatch_graph') as temp_file:
                timestamp = time.strftime(self.graph_args['time_format'])
                rrd_args = ["--full-size-mode",
                            "--start", start,
                            "--end", end,
                            "--watermark", f'{self.graph_args["name"]} :: {timestamp}',
                            "--width", str(self.graph_args["wide"])
                            ]
                if graph[:4] == 'pin-':
                    rrd_args.extend(["--height", str(self.graph_args["high"]/2)])
                else:
                    rrd_args.extend(["--height", str(self.graph_args["high"])])
                rrd_args.extend(["--title", f'{params[0]}: {duration}',
                                 "--upper-limit", params[1],
                                 "--lower-limit", params[2],
                                 "--left-axis-format", params[3]])
                if len(params) > 4:
                    rrd_args.extend(params[4:])
                rrd_args.extend([f'DEF:data={str(self.db_file)}:{graph}:AVERAGE',
                                 *self.graph_args["style"]])
                try:
                    rrdtool.graph(
                            temp_file.name,
                            *rrd_args)
                except Exception as rrd_error:
                    print("RRDTool graph error:")
                    print(rrd_error)
                response = temp_file.read()
                if len(response) == 0:
                    print(f'Error: png file generation failed for : {graph} : {start}>>{end}')
        else:
            print(f'Error: No graph available for type: {graph}')
        return response
