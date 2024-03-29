'''Data-Driven RRDB database handling for the SBCEye project
'''

# pragma pylint: disable=logging-fstring-interpolation

import time
from pathlib import Path
import logging
import gzip
import subprocess
import os
from shutil import which
from threading import Thread, Lock, local
import schedule
import rrdtool

# Dump and graph operations are run multithreaded by the httpServer, and backups
#  are also threaded. We need some mutex locks for them
db_lock = Lock()
dump_local = local()
graph_local = local()

class Robin:
    '''Helper class for RRDB database
    '''

    def __init__(self, s, data):
        self.graph_args = {}
        self.graph_args["name"] = s.name
        self.graph_args["time_format"] = s.long_format
        self.graph_args["time_stamp"] = s.short_format
        self.graph_args["wide"] = s.graph_wide
        self.graph_args["high"] = s.graph_high
        self.graph_args["line_color"] = s.graph_line_color
        self.graph_args["line_width"] = s.graph_line_width
        self.graph_args["area_color"] = s.graph_area_color
        self.graph_args["area_depth"] = s.graph_area_depth
        self.half_height = s.graph_half_height


        # Sensor and system sources with limits (min,max)
        self.data_sources = {
                'env-temp': ('-40','80'),
                'env-humi': ('0','100'),
                'env-pres': ('300','1100'),
                'sys-temp': ('-10','110'),
                'sys-load': ('0','100'),
                'sys-freq': ('1','U'),
                'sys-mem': ('0','110'),
                'sys-disk': ('0','110'),
                'sys-proc': ('0','U'),
                'sys-net-io': ('0','U'),
                'sys-disk-io': ('0','U'),
                'sys-cpu-int': ('0','U'),
            }

        # Graphs and parameters
        self.graph_map = {
                'env-temp': (f'{s.web_sensor_name} Temperature, \u00B0Centigrade',
                    None, None, '%3.0lf\u00B0', '%3.1lf\u00B0C'),
                'env-humi': (f'{s.web_sensor_name} Humidity, % percent',
                    None, None, '%3.0lf', '%3.0lf%%'),
                'env-pres': (f'{s.web_sensor_name} Pressure, millibars',
                    None, None, '%4.0lf', '%4.0lf mb', '--units-exponent','0',
                    '--y-grid','25:1'),
                'sys-temp': ('CPU Temperature, \u00B0Centigrade',
                    None, None, '%3.0lf\u00B0', '%3.1lf\u00B0C'),
                'sys-load': ('CPU Load Average',
                    None, '0','%3.1lf', '%3.2lf', '--units-exponent','0'),
                'sys-freq': ('CPU frequency, MHz',
                    None, None, '%4.0lf', '%4.0lf MHz', '--units-exponent','0'),
                'sys-mem':  ('System Memory Use, % percent',
                    '100', '0', '%3.0lf', '%3.0lf%%'),
                'sys-disk': ('System Disk use, % percent',
                    '100', '0', '%3.0lf', '%3.0lf%%'),
                'sys-proc': ('System Process count',
                    None, None, '%4.0lf', '%4.0lf'),
                'sys-net-io': ('System network IO, k/s',
                    None, None, '%5.0lf', '%5.0lf k/s', '--units-exponent','0'),
                'sys-disk-io': ('System disk IO, k/s',
                    None, None, '%5.0lf', '%5.0lf k/s', '--units-exponent','0'),
                'sys-cpu-int': ('CPU Soft interrupts, per second',
                    None, None, '%5.0lf', '%5.0lf /s', '--units-exponent','0'),
                }
        # connectivity
        for host in s.net_map.keys():
            self.data_sources[f'net-{host}'] = ('0','U')
            self.graph_map[f'net-{host}'] = (f'{host} Ping, milliseconds',
                    '25', '0' ,'%3.0lf', '%3.1lf ms', '--alt-autoscale', '--units-exponent','0')

        # pins
        for name in s.pin_map.keys():
            self.data_sources[f'pin-{name}'] = ('0','1')
            self.graph_map[f'pin-{name}'] = (f'{name} Pin State, '\
                    f'0 = {s.pin_state_names[0]}, 1 = {s.pin_state_names[1]}',
                    '1', '0' ,'%3.1lf', '%3.0lf', '--alt-autoscale', '--units-exponent','0')

        # set the list of active and storable sources
        self.template= ''
        self.sources = []
        for source,_ in self.data_sources.items():
            if source in data.keys():
                self.sources.append(source)
                self.template += f'{source}:'
        self.template = self.template.rstrip(':')
        print(f'RRD Sources = {self.template}')

        # Backup settings
        self.backup_count = s.rrd_backup_count
        self.backup_age = s.rrd_backup_age
        self.backup_time = s.rrd_backup_time

        # File paths
        db_path = Path(f'{s.rrd_dir}').resolve()
        self.db_file = Path(f'{s.rrd_dir}/{s.rrd_file_name}').resolve()
        source_file = Path(f'{s.rrd_dir}/{s.rrd_file_name}.old').resolve()
        if s.rrd_backup_count > 0:
            try:
                os.mkdir(f'{str(db_path)}/backup/')
            except FileExistsError:
                pass
            except OSError:
                logging.warning('Disabling database backups because the'\
                        'backup folder could not be created')
                print(f'Database backup folder creation failed ({str(db_path)}/backup/)')
                self.backup_count = 0
            self.backup_path = str(Path(f'{s.rrd_dir}/backup/').resolve())
            self.backup_name = f'{s.rrd_file_name}'

        # Database
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
                    "RRA:AVERAGE:0.5:6:133920",    # 3 months per minute
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

        # Disable dumping if rrdtool not in path
        self.rrdtool = which("rrdtool")
        if self.rrdtool:
            print(f'Commandline rrdtool: {self.rrdtool}')
        else:
            print('No commandline rrdtool available, ' + 'graphing and dumping disabled')

        # Use a home-brew local cache
        self.cache = []
        self.last_write = 0
        self.cache_age = s.rrd_interval

        # Notify
        print('RRD database and cache configured and enabled')
        logging.info(f'RRD database is: {str(self.db_file)}')


    def _backup(self):
        '''Backup and rotate old backups'''
        if self.backup_count > 0:
            # Copy to a timestamped file
            self.write_updates()
            suffix = time.strftime("%Y-%m-%d.%H:%M:%S.gz")
            if not db_lock.acquire(blocking=True, timeout=600):
                print('Error: Backup failed, could not acquire db lock within 600s')
                return
            start = time.time()
            with open(f'{self.db_file}', 'rb') as dbfile:
                with gzip.GzipFile(
                        f'{str(self.backup_path)}/{self.backup_name}.{suffix}',
                        mode = 'wb', compresslevel = 6) as zipfile:
                    zipfile.write(dbfile.read())
            db_lock.release()
            #logging.info(f'Database backup saved as: {self.backup_name}.{suffix}')
            print(f'Database backup saved as: {self.backup_name}.{suffix} '\
                    f'(took: {(time.time() - start):.2f}s)')

            # Process old backups
            now = time.time()
            candidates = {}
            retain = 0
            for entry in os.scandir(self.backup_path):
                if entry.name.startswith(f'{self.backup_name}.'):
                    age = now - os.stat(entry).st_mtime
                    if age > self.backup_age:
                        candidates[entry.name] = age
                    else:
                        retain += 1
            for name,age in sorted(candidates.items(), key=lambda x: x[1]):
                if retain < self.backup_count:
                    retain += 1
                else:
                    os.remove(f'{self.backup_path}/{name}')
                    #logging.info(f'Removed stale backup: {name}')
                    print(f'Removed stale backup: {name}')

    def start_backups(self):
        '''Add the backup schedule job'''
        # Start the backup schedule, using threads since it can run for some time
        if self.backup_count > 0:
            schedule.every().day.at(self.backup_time).do(run_threaded, self._backup)

    def dump(self):
        '''provide a gzipped dump of database'''
        dump_local.zipped = bytearray()
        if self.rrdtool:
            self.write_updates()
            print('Dump requested')
            if not db_lock.acquire(blocking=True, timeout=60):
                print('Error: Dumping failed, could not acquire db lock within 60s')
                return dump_local.zipped
            dump_local.start = time.time()
            dump = subprocess.check_output([self.rrdtool, 'dump', str(self.db_file)])
            db_lock.release()
            print(f'Dump is: {len(dump)} bytes raw and '\
                    f'took {(time.time() - dump_local.start):.2f}s')
            dump_local.start = time.time()
            dump_local.zipped = gzip.compress(dump, compresslevel=6)
            print(f'Dump compressed to {len(dump_local.zipped)} bytes '\
                    f'in {(time.time() - dump_local.start):.2f}s')
        else:
            print('Dump requested but denied because commandline "rrdtool" unavailable')
        return dump_local.zipped

    def update(self, data):
        '''Update the database with the latest readings'''
        dataline = str(int(time.time()))
        for source in self.sources:
            dataline += f':{data[source]}'
        self.cache.append(dataline)
        if time.time() > (self.last_write + self.cache_age)\
                and not db_lock.locked():
            self.write_updates()

    def write_updates(self):
        '''write any cached updates to the database'''
        if len(self.cache) > 0:
            if not db_lock.acquire(blocking=True, timeout=self.cache_age):
                print('Error: Data Write failed, could not acquire database '\
                        f'lock within write period ({self.cache_age}s)')
                return
            # check if cache was emptied in another thread while waiting for lock
            if len(self.cache) > 0:
                # print(f'DB WRITE:len={len(self.cache)}')
                try:
                    rrdtool.update(
                            str(self.db_file),
                            "--template", self.template,
                            "--skip-past-updates",
                            *self.cache)
                    self.cache = []
                except rrdtool.OperationalError as rrd_error:
                    print("RRDTool update error:")
                    print(rrd_error)
            db_lock.release()
        self.last_write = time.time()

    def draw_graph(self, start, end, duration, graph):
        '''Generate a graph, returns a raw png image'''
        graph_local.response = bytearray()
        if (graph in self.sources) and (graph in self.graph_map.keys()):
            self.write_updates()
            params = self.graph_map[graph]
            timestamp = time.strftime(self.graph_args['time_format'])
            duration = duration.replace('now',
                    f'{time.strftime(self.graph_args["time_stamp"])}')
            rrd_args = ["--full-size-mode",
                        "--start", start,
                        "--end", end,
                        "--watermark",
                        f'{self.graph_args["name"]} :: {graph} :: {timestamp}',
                        "--width", str(self.graph_args["wide"])
                        ]
            if graph.split('-')[0] in self.half_height:
                rrd_args.extend(["--height", str(self.graph_args["high"]/2)])
            else:
                rrd_args.extend(["--height", str(self.graph_args["high"])])
            rrd_args.extend(["--title", f'{params[0]}: {duration}'])
            if params[1]:
                rrd_args.extend(["--upper-limit", params[1]])
            if params[2]:
                rrd_args.extend(["--lower-limit", params[2]])
            rrd_args.extend(["--left-axis-format", params[3]])
            if len(params) > 5:
                rrd_args.extend(params[5:])
            rrd_args.extend([f'DEF:data={str(self.db_file)}:{graph}:AVERAGE'])
            if self.graph_args["area_color"]:
                rrd_args.extend([f'AREA:data{self.graph_args["area_color"]}:'\
                        f'gradheight={self.graph_args["area_depth"]}'])
            rrd_args.extend([f'LINE{self.graph_args["line_width"]}:'\
                    f'data{self.graph_args["line_color"]}:'\
                    f'{self.graph_args["name"]}',
                    rf'GPRINT:data:MIN:Min\:{params[4]}',
                    rf'GPRINT:data:AVERAGE:Average\:{params[4]}',
                    rf'GPRINT:data:MAX:Max\:{params[4]}',
                    rf'GPRINT:data:LAST:Last\:{params[4]}'])
            rrd_args.extend(['COMMENT: ', 'COMMENT: '])

            try:
                graph_local.response = subprocess.check_output(
                        [self.rrdtool, 'graph', '-', *rrd_args])
            except subprocess.CalledProcessError as graph_error:
                print(f'Graph generation failed:\n{graph_error}')
                print(f'cmd: {graph_error.cmd}')
                print(f'output: {graph_error.output}')
                print(f'stdout: {graph_error.stderr}')

            if len(graph_local.response) == 0:
                print(f'Error: png file generation failed for : {graph} : {start}>>{end}')
        else:
            print(f'Error: No graph available for type: {graph}')
        return graph_local.response

def run_threaded(job_func):
    '''Start a job in a new thread
    '''
    job_thread = Thread(target=job_func)
    job_thread.start()
