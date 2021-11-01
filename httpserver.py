# Provides the http handler and request server for the Pi OverWatch

import sys
import os.path
import datetime
import subprocess
import re

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread, current_thread

# Logging
import logging

# RRD data
from robin import Robin, get_period

def serve_http(s, rrd, data, helpers):
    # Spawns a http.server.HTTPServer in a separate thread on the given port.
    handler = _BaseRequestHandler
    httpd = http.server.HTTPServer((s.web_host, s.web_port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well (left here to make obvious).
    httpd.allow_reuse_address = True
    # I'm just passing objects blindly into the http class itself, quick and dirty but it works
    # there is probably a better way to do this, eg using a meta-class and inheritance
    http.s = s
    http.rrd = rrd
    http.data = data
    http.button_control = helpers[0]
    http.update_data = helpers[1]
    http.update_pins = helpers[2]
    # Start the server
    _threadlog(f"HTTP server will bind to port {str(s.web_port)} on host {s.web_host}")
    httpd.server_bind()
    address = f"http://{httpd.server_name}:{httpd.server_port}"
    _threadlog(f"Access via: {address}")
    print(f"Webserver started on : {address}")
    httpd.server_activate()
    def serve_forever(httpd):
        with httpd:  # to make sure httpd.server_close is called
            _threadlog("Http Server start")
            httpd.serve_forever()
            _threadlog("Http Server closing down")
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.setDaemon(True)
    thread.start()
    return httpd, address

def _threadlog(logline):
    # A wrapper function around logging.info() that prepends the current thread name
    logging.info(f"[{current_thread().name}] : {logline}")

class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):
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

    def _set_icon_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "image/x-icon")
        self.end_headers()

    def _give_head(self, title_extra=""):
        title = http.s.name
        if len(title_extra) > 0:
            title = f"{http.s.name}{title_extra}"
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
        # DEBUG: f'<pre style="color:#888888">GET: {self.path} from: {self.client_address[0]}</pre>\n'
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

    def _give_datetime(self):
        timestamp = datetime.datetime.now().strftime(http.s.time_format)
        return  f'''<div style="color:#555555;
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
                'env-humi': ('Humidity','.1f','%'),
                'env-pres': ('Presssure','.0f','mb'),
                }
        ret = ''
        if len(http.data.keys() & sensorlist.keys()) > 0:
            ret += f'<tr><th>{http.s.web_sensor_name}</th></tr>\n'
            for sense,(name,fmt,suffix) in sensorlist.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td>{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
        return ret

    def _give_sys(self):
        # Internal Sensors
        sensorlist = {
                'sys-temp': ('CPU Temperature','.1f','&deg;'),
                'sys-load': ('CPU Load','1.2f',''),
                'sys-mem': ('Memory used','.1f','%'),
                }
        ret = ''
        if len(http.data.keys() & sensorlist.keys()) > 0:
            ret = '<tr><th>Server</th></tr>\n'
            for sense,(name,fmt,suffix) in sensorlist.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td>{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
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
                ret += f'<tr><td>{name}:</td><td>'\
                       f'{http.s.web_pin_states[bool(http.data[sense])]}</td></tr>\n'
        return ret

    def _give_graphlinks(self, skip=""):
        # A list of available graph pages
        ret = ''
        skip = skip.lstrip('-')
        if len(http.s.graph_durations) > 0:
            if len(skip) == 0:
                ret += '<tr><th>Graphs</th></tr>\n'
            ret += '<tr><td colspan="2" style="text-align: center;">\n'
            for duration in http.s.graph_durations:
                if duration != skip:
                    ret += f'&nbsp;<a href="./graphs?start=-{duration}" '\
                           f'title="Graphs covering the last {duration} in time">'\
                           f'{duration}</a>&nbsp;\n'
                else:
                    ret += f'&nbsp;<span style="color: #BBBBBB;">{duration}</span>&nbsp;\n'
            if len(skip) > 0:
                ret += '&nbsp;:&nbsp;&nbsp;<a href="./" title="Main page">Home</a>\n'
            ret += '</td></tr>\n'
        return ret

    def _give_links(self):
        # Currently just a link to the log
        return f'''{self._give_graphlinks()}
                <tr>
                <td colspan="2" style="text-align: center;">
                <a href="./?view=deco&view=log" title="Open the log in a new page" target="_blank">
                Log</a>
                </td>
                </tr>'''

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
        log_command = f"for a in `ls -tr {http.s.log_file}*`;do cat $a ; done | tail -{lines}"
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

    def _give_graphs(self, start, end, period):
        ret = f'''<table>\n
                <tr><th>Graphs: {period}</th></tr>\n'''
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

    def _write_dedented(self, html):
        # Strip leading whitespace and write
        response = re.sub(r'^\s*','', html, flags=re.MULTILINE)
        self.wfile.write(bytes(response, 'utf-8'))


    def do_GET(self):
        # Process requests and parse their options
        if urlparse(self.path).path == '/graph':
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
                else:
                    end = parsed_end[0]
                body = Robin.draw_graph(http.rrd, start, end, graph)
            if len(body) == 0:
                self.send_error(404, 'Graph unavailable',
                        'Check your parameters and try again,'\
                        'see the "/graphs/" page for examples.')
                return
            self._set_png_headers()
            self.wfile.write(body)
        elif urlparse(self.path).path == '/graphs':
            parsed_start = parse_qs(urlparse(self.path).query).get('start', None)
            parsed_end = parse_qs(urlparse(self.path).query).get('end', None)
            # Graph Index Page
            if not parsed_start:
                start = "end-1d"
            else:
                start = parsed_start[0]
            if not parsed_end:
                end =''
            else:
                end = parsed_end[0]
            period = get_period(start, end)
            self._set_headers()
            response = self._give_head(f" :: graphs {period}")
            response += f'<h2>{http.s.name}</h2>'
            response += self._give_graphs(start, end, period)
            response += self._give_datetime()
            response += self._give_foot(refresh=300)
            self._write_dedented(response)
        elif urlparse(self.path).path == '/favicon.ico':
            print('ICON')
            fi_file = 'favicon.ico'
            if not os.path.exists(fi_file):
                fi_file = f'{sys.path[0]}/{fi_file}'
            print(fi_file)
            if not os.path.exists(fi_file):
                self.send_error(404, 'unavailable',
                        f'{fi_file} not found.')
            else:
                self._set_icon_headers()
                with open(fi_file,'rb') as fi:
                    self.wfile.write(fi.read())
        elif ((urlparse(self.path).path == '/' + http.s.button_url)
                and (len(http.s.button_url) > 0)
                and (len(http.s.pin_map.keys()) > 0)):
            # Web Button
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
            status, state, name = http.button_control(action)
            if not status == f'{name} : {http.s.web_pin_states[state]}':
                logging.info(f'Web button triggered by: {self.client_address[0]}'\
                            f' with action: {action}')
            self._set_headers()
            response = self._give_head(f" :: {name}")
            response += f'<h2>{status}</h2>\n'
            invert_state = http.s.web_pin_states[not state]
            response += f'''<div>
                    <a href="./{http.s.button_url}?state={invert_state}"
                    title = "Switch {name} {invert_state}">
                    Switch {invert_state}</a>
                    </div>\n'''
            response += '<div style="padding-top: 1em;">\n'\
                    '<a href="./" title="Main page">Home</a></div>\n'
            response += self._give_datetime()
            response += '<script>\n'\
                    'setTimeout(function(){location.replace(location.pathname);}, '\
                    '60000);\n</script>\n'
            response += self._give_foot()
            self._write_dedented(response)
        elif urlparse(self.path).path == '/':
            # Main Page
            http.update_data()
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if not view:
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            response = self._give_head()
            scroll_page = False
            if "deco" in view:
                response += f'<h2>{http.s.name}</h2>\n'
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
                response += self._give_datetime()
            response += self._give_foot(refresh= 60, scroll= scroll_page)
            self._write_dedented(response)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at "/" and "/graphs"')

    def do_HEAD(self):
        self._set_headers()
