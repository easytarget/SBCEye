'''Provides the threaded http handler for the Pi OverWatch
'''

# pragma pylint: disable=logging-fstring-interpolation,no-self-use

import sys
import os.path
import time
import subprocess
import re

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread, local

# Logging
import logging

def serve_http(settings, rrd, data, helpers):
    '''Spawns a http.server.HTTPServer in a separate thread on the given port'''
    handler = _BaseRequestHandler
    httpd = http.server.ThreadingHTTPServer((settings.web_host, settings.web_port), handler, False)
    #httpd = http.server.HTTPServer((settings.web_host, settings.web_port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well (left here to make obvious).
    httpd.allow_reuse_address = True
    # I'm just passing objects blindly into the http class itself, quick and dirty but it works
    # there is probably a better way to do this, eg using a meta-class and inheritance
    http.settings = settings
    http.rrd = rrd
    http.data = data
    http.button_control = helpers[0]
    http.update_pins = helpers[1]
    http.icon_file = 'favicon.ico'
    if not os.path.exists(http.icon_file):
        http.icon_file = f'{sys.path[0]}/{http.icon_file}'
    if rrd.rrdtool:
        http.db_graphable = True
        if settings.web_allow_dump:
            logging.info("RRD database is dumpable via web")
            http.db_dumpable = True
        else:
            http.db_dumpable = False
    else:
        logging.warning('Commandline rrdtool not found, '\
                'graphing and dumping functions are unavailable')
        http.db_dumpable = False
        http.db_graphable = False

    # Start the server
    logging.info(f'HTTP server will bind to port {str(settings.web_port)} '\
            f'on host {settings.web_host}')
    httpd.server_bind()
    address = f"http://{httpd.server_name}:{httpd.server_port}"
    print(f"Webserver starting on : {address}")
    httpd.server_activate()

    def serve_forever(httpd):
        with httpd:  # to make sure httpd.server_close is called
            logging.info("Http Server starting")
            httpd.serve_forever()
            logging.info("Http Server closing down")

    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.setDaemon(True )
    thread.start()


class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):
    '''Handles each individual request in a new thread'''

    def _set_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def _set_png_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "image/png")
        self.send_header("Cache-Control", "max-age=60")
        self.end_headers()

    def _set_download_headers(self, size, name):
        self.send_response(200)
        self.send_header("Content-Type", 'application/octet-stream')
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(size))
        self.end_headers()

    def _set_icon_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "image/x-icon")
        self.end_headers()

    def _give_head(self, title_extra=""):
        title = http.settings.name
        if len(title_extra) > 0:
            title = f"{http.settings.name}{title_extra}"
        return f'''
                <!DOCTYPE html>
                <html>
                <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>{title}</title>
                <style>
                body {{display:flex; flex-direction: column; align-items: center;}}
                a {{color:#555555; text-decoration: none;}}
                img {{width:auto; max-width:100%;}}
                table {{border-spacing: 0.2em; width:auto; max-width:100%;}}
                th {{font-size: 110%; text-align: left;}}
                td {{padding-left: 1em;}}
                </style>
                </head>
                <body>'''

    def _give_foot(self, refresh = 0, scroll = False):
        ret = '''</body>\n
                <script>\n'''
        if refresh > 0:
            ret += 'setTimeout(function(){location.replace(document.URL);}, '\
                    f'{str(refresh*1000)});\n'
        if scroll:
            ret += '''function down() {
                        window.scrollTo(0,document.body.scrollHeight);
                        console.log("SCROLL" + document.body.scrollHeight);
                    }
                    window.onload = down;'''
        ret += '''</script>
                </html>'''
        return ret

    def _give_timestamp(self):
        timestamp = time.strftime(http.settings.long_format,
                time.localtime(http.data["update-time"]))
        return  f'''<div title="Time of latest data readings"
                style="color:#555555;
                font-size: 94%; padding-top: 0.5em;">{timestamp}</div>
                <div style="color:#888888;
                font-size: 66%; font-weight: lighter; padding-top:0.5em">
                <a href="https://github.com/easytarget/pi-overwatch"
                title="Project homepage on GitHub" target="_blank">
                OverWatch</a></div>'''

    def _give_env(self):
        # Environmental sensor
        sensorlist = {
                'env-temp': ('Temperature','.1f','&deg;'),
                'env-humi': ('Humidity','.1f','<span style="font-size: 75%;">%</span>'),
                'env-pres': ('Presssure','.0f','<span style="font-size: 75%;"> mb</span>'),
                }
        ret = ''
        if len(http.data.keys() & sensorlist.keys()) > 0:
            ret += f'<tr><th>{http.settings.web_sensor_name}</th></tr>\n'
            for sense,(name,fmt,suffix) in sensorlist.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td style="text-align: right;">'\
                            f'{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
        return ret

    def _give_sys(self):
        # Internal Sensors
        sensorlist = {
                'sys-temp': ('CPU Temperature','.1f','&deg;'),
                'sys-load': ('CPU Load','1.2f',''),
                'sys-freq': ('CPU Frequency','.0f','<span style="font-size: 75%;"> MHz</span>'),
                'sys-mem': ('Memory used','.1f','<span style="font-size: 75%;">%</span>'),
                'sys-disk': ('Disk used','.1f','<span style="font-size: 75%;">%</span>'),
                'sys-proc': ('Processes','.0f',''),
                'sys-net-io': ('Network IO','.1f','<span style="font-size: 75%;"> k/s</span>'),
                'sys-disk-io': ('Disk IO','.1f','<span style="font-size: 75%;"> k/s</span>'),
                'sys-cpu-int': ('Soft Interrupts','.0f','<span style="font-size: 75%;"> /s</span>'),
                }
        ret = ''
        if len(http.data.keys() & sensorlist.keys()) > 0:
            ret = '<tr><th>Server</th></tr>\n'
            for sense,(name,fmt,suffix) in sensorlist.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td style="text-align: right;">'\
                            f'{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
        return ret

    def _give_pins(self):
        # GPIO states
        ret = ''
        pinlist = {}
        for key in http.data.keys():
            if key[0:4] == 'pin-':
                pinlist[key] = key[4:]
        if len(http.data.keys() & pinlist.keys()) > 0:
            ret += '<tr><th>GPIO</th></tr>\n'
            for sense,name in pinlist.items():
                ret += f'<tr><td>{name}:</td><td style="text-align: right;">'\
                       f'{http.settings.web_pin_states[bool(http.data[sense])]}</td></tr>\n'
        return ret

    def _give_graphlinks(self, skip=""):
        # A list of available graph pages
        ret = ''
        skip = skip.lstrip('-')
        if (len(http.settings.graph_durations) > 0) and http.db_graphable:
            if len(skip) == 0:
                ret += '<tr><th>Graphs</th></tr>\n'
            ret += '<tr><td colspan="2" style="text-align: center;">\n'
            for duration in http.settings.graph_durations:
                if duration != skip:
                    ret += f'&nbsp;<a href="./graphs?start=end-{duration}" '\
                           f'title="Graphs covering the last {duration} in time">'\
                           f'{duration}</a>&nbsp;\n'
                else:
                    ret += f'&nbsp;<span style="color: #BBBBBB;">{duration}</span>&nbsp;\n'
            if len(skip) > 0:
                ret += '&nbsp;:&nbsp;&nbsp;<a href="./" title="Main page">Home</a>\n'
            ret += '</td></tr>\n'
        return ret

    def _give_links(self):
        # Link to the log and pin contol pages
        ret = f'''{self._give_graphlinks()}
                <tr><td colspan="2" style="text-align: center;">
                <a href="./?view=deco&view=log" title="Open log in a new page" target="_blank">
                Log</a>\n'''
        if http.settings.web_show_control and (http.settings.button_pin > 0):
            ret += f'&nbsp;&nbsp;<a href="./{http.settings.button_url}" '\
                    f'title="{http.settings.button_name} status and control page">'\
                    f'{http.settings.button_name}</a>\n'
        ret += '</td></tr>\n'
        return ret

    def _give_log(self, lines=100):
        # Combine and give last (lines) lines of log
        parsed_lines = parse_qs(urlparse(self.path).query).get('lines', None)
        if isinstance(parsed_lines, list):
            lines = parsed_lines[0]
        # Do not pass anything other than integers to the shell commsnd..
        if not isinstance(lines, int):
            try:
                lines = int(lines)
            except ValueError:
                lines = int(100)
        lines = max(1, min(lines, 250000))
        # Use a shell one-liner used to extract the last {lines} of data from the logs
        # There is doubtless a more 'python' way to do this, but it is fast, cheap and works..
        log_command = \
                f"for a in `ls -tr {http.settings.log_file}*`;do cat $a ; done | tail -{lines}"
        log = subprocess.check_output(log_command, shell=True).decode('utf-8')
        ret = f'''
                <div style="overflow-x: auto; width: 100%;">\n
                <span style="font-size: 110%; font-weight: bold;">Recent log activity:</span>
                <hr><pre>\n{log}</pre><hr>
                <span style="font-size: 80%;">Latest {lines} lines shown</span>\n
                </div>\n
                <div><a href="./?view=deco&view=log&lines=25" title="show 25 lines">25</a>&nbsp;:
                &nbsp;<a href="./?view=deco&view=log&lines=250" title="show 250 lines">250</a>&nbsp;:
                &nbsp;<a href="./?view=deco&view=log&lines=2500" title="show 2500 lines">2500</a>&nbsp;:
                &nbsp;<a href="./" title="Main page">Home</a></div>\n'''
        return ret

    def _give_graphs(self, start, end, stamp):
        ret = f'''<table>\n
                <tr><th>Graphs: {stamp}</th></tr>\n'''
        for graph,(title,*_) in http.rrd.graph_map.items():
            if graph in http.rrd.sources:
                ret += f'''<tr><td>\n
                        <a href="graph?graph={graph}&start={start}&end={end}">
                        <img title="{title}"
                        src="graph?graph={graph}&start={start}&end={end}"></a>\n
                        </td></tr>\n'''
        ret += self._give_graphlinks(skip=start)
        ret += '</table>\n'
        return ret

    def _give_dump_portal(self):
        return '''
                <h2>RRD database dump in gzipped XML format</h2>
                <div style="text-align: center; width: 80%">What is this?
                See: <a href="https://oss.oetiker.ch/rrdtool/doc/rrddump.en.html"
                title = "RRDTool documentation" target="_blank">The Docs</a>
                </div>
                <div style="text-align: center;">
                <hr>
                Generating the dump imposes a high load on the overwatch process and
                can potentially impact other software running on the system.
                <br>
                It can take several minutes to complete; depending on the
                host machine and db size+complexity. <em>Use with care!</em>
                <hr>
                If you are sure you wish to proceed:<br>
                <a href="./dump_gz" title = "Direct download link">Download</a>
                </div>
                '''

    def _write_dedented(self, html):
        # Strip leading whitespace and write
        response = re.sub(r'^\s*','', html, flags=re.MULTILINE)
        self.wfile.write(bytes(response, 'utf-8'))

    def do_GET(self):
        '''Process requests and parse their options'''
        if (urlparse(self.path).path == '/graph') and http.db_graphable:
            # Individual Graph
            parsed_graph = parse_qs(urlparse(self.path).query).get('graph', None)
            parsed_start = parse_qs(urlparse(self.path).query).get('start', None)
            parsed_end = parse_qs(urlparse(self.path).query).get('end', None)
            if not parsed_graph:
                body = ""
            else:
                graph = parsed_graph[0]
                if not parsed_start:
                    start = "end-1d"
                else:
                    start = parsed_start[0]
                if not parsed_end:
                    end = "now"
                    stamp = f'{start.replace("end","")} >> now'
                else:
                    end = parsed_end[0]
                    stamp = f'{start} >> {end}'
                body = http.rrd.draw_graph(start, end, stamp, graph)
            if len(body) == 0:
                self.send_error(404, 'Graph unavailable',
                        'Check your parameters and try again,'\
                        'see the "/graphs/" page for examples.')
                return
            self._set_png_headers()
            self.wfile.write(body)
        elif (urlparse(self.path).path == '/graphs') and http.db_graphable:
            # Graph Index Page
            parsed_start = parse_qs(urlparse(self.path).query).get('start', None)
            parsed_end = parse_qs(urlparse(self.path).query).get('end', None)
            if not parsed_start:
                start = "end-1d"
            else:
                start = parsed_start[0]
            if not parsed_end:
                end =''
                stamp = f'{start.replace("end","")} >> now'
            else:
                end = parsed_end[0]
                stamp = f'{start} >> {end}'
            self._set_headers()
            response = self._give_head(f" :: graphs {stamp}")
            response += f'<h2>{http.settings.name}</h2>'
            response += self._give_graphs(start, end, stamp)
            response += self._give_timestamp()
            response += self._give_foot(refresh=300)
            self._write_dedented(response)
        elif urlparse(self.path).path == '/favicon.ico':
            # Favicon
            if not os.path.exists(http.icon_file):
                self.send_error(404, 'unavailable',
                        f'{http.icon_file} not found.')
            else:
                self._set_icon_headers()
                with open(http.icon_file,'rb') as favicon:
                    self.wfile.write(favicon.read())
        elif ((urlparse(self.path).path == '/' + http.settings.button_url)
                and (len(http.settings.button_url) > 0)
                and (http.settings.button_out > 0)):
            # Web button control
            http.update_pins()
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if parsed:
                action = parsed[0]
            elif urlparse(self.path).query:
                self.send_error(404, 'Unknown Parameters',
                        'This URL takes a single parameter: "?state=<new state>"')
                return
            else:
                action = 'status'
            status, state = http.button_control(action)
            if not status == f'{http.settings.button_name} : {http.settings.web_pin_states[state]}':
                logging.info(f'Web button triggered by: {self.client_address[0]}'\
                            f' with action: {action}')
            self._set_headers()
            response = self._give_head(f" :: {http.settings.button_name}")
            response += f'<h2>{status}</h2>\n'
            invert_state = http.settings.web_pin_states[not state]
            response += f'''<div>
                    <a href="./{http.settings.button_url}?state={invert_state}"
                    title = "Switch {http.settings.button_name} {invert_state}">
                    Switch {invert_state}</a>
                    </div>\n'''
            response += '<div style="padding-top: 1em;">\n'\
                    '<a href="./" title="Main page">Home</a></div>\n'
            response += self._give_timestamp()
            response += '<script>\n'\
                    'setTimeout(function(){location.replace(location.pathname);}, '\
                    '60000);\n</script>\n'
            response += self._give_foot()
            self._write_dedented(response)
        elif (urlparse(self.path).path == '/dump_gz') and http.db_dumpable:
            # Raw dump download
            start = time.time()
            logging.info(f"RRD database dump requested by {self.client_address[0]}")
            response = http.rrd.dump()
            self._set_download_headers(len(response),
                    f'{http.settings.name}-rrd-{time.strftime("%Y%m%d-%H%M%S")}.xml.gz')
            self.wfile.write(response)
            logging.info(f"Dump completed in {(time.time() - start):.2f}s")
        elif (urlparse(self.path).path == '/dump') and http.db_dumpable:
            # Dump warning and link page
            self._set_headers()
            response = self._give_head(" :: RRD Dump")
            response += self._give_dump_portal()
            response += self._give_foot()
            self._write_dedented(response)
        elif urlparse(self.path).path == '/':
            # Main Page
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if not view:
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            response = self._give_head()
            scroll_page = False
            if "deco" in view:
                response += f'<h2>{http.settings.name}</h2>\n'
            response += '<table>\n'
            if "env" in view:
                response += self._give_env()
            if "sys" in view:
                response += self._give_sys()
            if "gpio" in view:
                response += self._give_pins()
            if "links" in view:
                response += self._give_links()
            response += '</table>\n'
            if "log" in view:
                response += self._give_log()
                scroll_page = True
            if "deco" in view:
                response += self._give_timestamp()
            response += self._give_foot(refresh= 60, scroll= scroll_page)
            self._write_dedented(response)
        else:
            self.send_error(404, 'No Such Page', 'Nothing matches the given URL on this OverWatch server')

    def do_HEAD(self):
        '''returns headers'''
        self._set_headers()
