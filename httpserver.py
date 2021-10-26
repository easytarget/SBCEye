# Provides the http handler and request server for the Pi OverWatch

import datetime
import subprocess

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread, current_thread

# Logging
import logging

# RRD data
from robin import Robin

def serve_http(s, rrd, data, toggle_button):
    # Spawns a http.server.HTTPServer in a separate thread on the given port.
    handler = _BaseRequestHandler
    httpd = http.server.HTTPServer((s.host, s.port), handler, False)
    # Block only for 0.5 seconds max
    httpd.timeout = 0.5
    # HTTPServer sets this as well (left here to make obvious).
    httpd.allow_reuse_address = True
    # I'm just passing objects blindly into the http class itself, quick and dirty but it works
    # there is probably a better way to do this, eg using a meta-class and inheritance
    http.s = s
    http.rrd = rrd
    http.data = data
    http.toggle_button = toggle_button
    # Start the server
    threadlog(f"HTTP server will bind to port {str(s.port)} on host {s.host}")
    httpd.server_bind()
    address = f"http://{httpd.server_name}:{httpd.server_port}"
    threadlog(f"Access via: {address}")
    print(f"Webserver started on`: {address}")
    httpd.server_activate()
    def serve_forever(httpd):
        with httpd:  # to make sure httpd.server_close is called
            threadlog("Http Server start")
            httpd.serve_forever()
            threadlog("Http Server closing down")
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.setDaemon(True)
    thread.start()
    return httpd, address

def threadlog(logline):
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

    def _give_head(self, title_extra=""):
        title = http.s.server_name
        if len(title_extra) > 0:
            title=f"{http.s.server_name}{title_extra}"
        self.wfile.write(bytes('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n', 'utf-8'))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">\n', 'utf-8'))
        self.wfile.write(bytes(f'<title>{title}</title>\n', 'utf-8'))
        self.wfile.write(bytes('<style>\n', 'utf-8'))
        self.wfile.write(bytes('body {display:flex; flex-direction: column; align-items: center;}\n', 'utf-8'))
        self.wfile.write(bytes('a {color:#666666; text-decoration: none;}\n', 'utf-8'))
        self.wfile.write(bytes('img {width:auto; max-width:100%;}\n', 'utf-8'))
        self.wfile.write(bytes('table {border-spacing: 0.2em; width:auto; max-width:100%;}\n', 'utf-8'))
        self.wfile.write(bytes('th {font-size: 110%; text-align: left;}\n', 'utf-8'))
        self.wfile.write(bytes('td {padding-left: 1em;}\n', 'utf-8'))
        self.wfile.write(bytes('</style>\n', 'utf-8'))
        self.wfile.write(bytes('</head>\n', 'utf-8'))
        self.wfile.write(bytes('<body>\n', 'utf-8'))

    def _give_foot(self,scroll = False, refresh = 0):
        # DEBUG: self.wfile.write(bytes('<pre style="color:#888888">GET: ' + self.path + ' from: ' + self.client_address[0] + '</pre>\n', 'utf-8'))
        self.wfile.write(bytes('</body>\n', 'utf-8'))
        self.wfile.write(bytes("<script>\n", 'utf-8'))
        if scroll:
            self.wfile.write(bytes('function down() {\n', 'utf-8'))
            self.wfile.write(bytes('    window.scrollTo(0,document.body.scrollHeight);\n', 'utf-8'))
            self.wfile.write(bytes('    console.log("SCROLL" + document.body.scrollHeight);\n', 'utf-8'))
            self.wfile.write(bytes('}\n', 'utf-8'))
            self.wfile.write(bytes('window.onload = down;\n', 'utf-8'))
        if refresh > 0:
            self.wfile.write(bytes(f'setTimeout(function(){{location.replace(document.URL);}}, {str(refresh*1000)});\n', 'utf-8'))
        self.wfile.write(bytes('</script>\n', 'utf-8'))
        self.wfile.write(bytes('</html>\n', 'utf-8'))

    def _give_datetime(self):
        timestamp = datetime.datetime.now().strftime(http.s.time_format)
        ret = f'<div style="color:#666666; font-size: 90%; padding-top: 0.5em;">{timestamp}</div>'\
                '<div style="color:#888888; font-size: 66%; font-weight: lighter; padding-top:0.5em">'\
                '<a href="https://github.com/easytarget/pi-overwatch"'\
                'title="Project homepage on GitHub" target="_blank">'\
                'OverWatch</a></div>\n'
        return ret

    def _give_env(self):
        # Environmental sensor
        SENSORLIST = {
                'env-temp': ('Temperature','.1f','&deg;'),
                'env-humi': ('Humidity','.1f','%'),
                'env-pres': ('Presssure','.0f','mb'),
                }
        if len(http.data.keys() & SENSORLIST.keys()) > 0:
            ret = f'<tr><th>{http.s.sensor_name}</th></tr>\n'
            for sense,(name,fmt,suffix) in SENSORLIST.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td>{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
            self.wfile.write(bytes(ret, 'utf-8'))

    def _give_sys(self):
        # Internal Sensors
        SENSORLIST = {
                'sys-temp': ('CPU Temperature','.1f','&deg;'),
                'sys-load': ('CPU Load','1.2f',''),
                'sys-mem': ('Memory used','.1f','%'),
                }
        if len(http.data.keys() & SENSORLIST.keys()) > 0:
            ret = '<tr><th>Server</th></tr>\n'
            for sense,(name,fmt,suffix) in SENSORLIST.items():
                if sense in http.data.keys():
                    ret += f'<tr><td>{name}: </td><td>{http.data[sense]:{fmt}}{suffix}</td></tr>\n'
            self.wfile.write(bytes(ret, 'utf-8'))

    def _give_pins(self):
        # GPIO states
        PINLIST = {}
        for key in http.data.keys():
            if key[0:4] == 'pin-':
                PINLIST[key] = key[4:]
        if len(http.data.keys() & PINLIST.keys()) > 0:
            ret = '<tr><th>GPIO</th></tr>\n'
            for sense,name in PINLIST.items():
                ret += f'<tr><td>{name}:</td><td>{http.s.pin_states[bool(http.data[sense])]}</td></tr>\n'
        return ret

    def _give_graphlinks(self, skip=""):
        if len(skip) == 0:
            self.wfile.write(bytes('<tr><th>Graphs</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr>', 'utf-8'))
        self.wfile.write(bytes('<td colspan="2" style="text-align: center;">', 'utf-8'))
        for g in http.s.default_graphs:
            if g != skip:
                self.wfile.write(bytes(f'&nbsp;<a href="./graphs?duration={g}" title="Graphs covering the last {g} in time">{g}</a>&nbsp;', 'utf-8'))
            else:
                self.wfile.write(bytes(f'&nbsp;<span style="color: #AAAAAA;">{g}</span>&nbsp;', 'utf-8'))
        if len(skip) > 0:
            self.wfile.write(bytes('&nbsp;:&nbsp;&nbsp;<a href="./" title="Main page">Home</a>', 'utf-8'))
        self.wfile.write(bytes('</td>', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))

    def _give_links(self):
        self._give_graphlinks()
        self.wfile.write(bytes('<tr>', 'utf-8'))
        self.wfile.write(bytes('<td colspan="2" style="text-align: center;"><a href="./?view=deco&view=log" title="Open the extended log in a new page" target="_blank">Main Log</a></td>', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))

    def _give_log(self, lines=100):
        parsed_lines = parse_qs(urlparse(self.path).query).get('lines', None)
        if isinstance(parsed_lines, list):
            lines = parsed_lines[0]
        # Do not pass anything other than integers to the shell commsnd..
        if not isinstance(lines, int):
            try:
                lines = int(lines)
            except ValueError:
                lines = int(100)
        lines = max(1, min(lines, 100000))
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

    def _give_graphs(self, duration):
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes(f'<tr><th>Graphs: {duration} -> now</th></tr>\n', 'utf-8'))
        for graph,(title, *_) in http.rrd.graph_map.items():
            if graph in http.rrd.sources:
                self.wfile.write(bytes(f'<tr><td><a href="graph?graph={graph}&duration={duration}">', 'utf-8'))
                self.wfile.write(bytes(f'<img title="{title}" src="graph?graph={graph}&duration={duration}">', 'utf-8'))
                self.wfile.write(bytes('</a></td></tr>\n', 'utf-8'))
        self._give_graphlinks(skip=duration)
        self.wfile.write(bytes('</table>\n', 'utf-8'))

    def do_GET(self):
        # Process requests and parse their options
        if urlparse(self.path).path == '/graph':
            # Individual Graph
            parsed_graph = parse_qs(urlparse(self.path).query).get('graph', None)
            parsed_duration = parse_qs(urlparse(self.path).query).get('duration', None)
            if not parsed_graph:
                body = ""
            elif not parsed_duration:
                body = ""
            else:
                graph = parsed_graph[0]
                duration = parsed_duration[0]
                body = Robin.draw_graph(http.rrd, duration, graph)
            if len(body) == 0:
                self.send_error(404, 'Graph unavailable', 'Check your parameters and try again, see the "/graphs/" page for examples.')
                return
            self._set_png_headers()
            self.wfile.write(body)
        elif urlparse(self.path).path == '/graphs':
            # Graph Index Page
            parsed = parse_qs(urlparse(self.path).query).get('duration', None)
            if not parsed:
                duration = "1d"
            else:
                duration = parsed[0]
            self._set_headers()
            self._give_head(f" :: graphs -{duration}")
            self.wfile.write(bytes(f'<h2>{http.s.server_name}</h2>', 'utf-8'))
            self._give_graphs(duration)
            self.wfile.write(bytes(self._give_datetime(), 'utf-8'))
            self._give_foot(refresh=300)
        elif ((urlparse(self.path).path == '/' + http.s.button_url)
                and (len(http.s.button_url) > 0)
                and (len(http.s.pin_map.keys()) > 0)):
            # Web Button
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if parsed:
                action = parsed[0]
            elif urlparse(self.path).query:
                self.send_error(404, 'Unknown Parameters',
                        'This URL takes a single parameter: "?state=<new state>"')
                return
            else:
                action = 'toggle'
            logging.info(f'Web button triggered by: {self.client_address[0]} with action: {action}')
            state = http.toggle_button(action)
            self._set_headers()
            self._give_head(f" :: {next(iter(http.s.pin_map))}")
            self.wfile.write(bytes(f'<h2>{state}</h2>\n', 'utf-8'))
            self.wfile.write(bytes('<div><a href="./" title="Main page">Home</a></div>\n', 'utf-8'))
            self.wfile.write(bytes(self._give_datetime(), 'utf-8'))
            self._give_foot()
        elif urlparse(self.path).path == '/':
            # Main Page
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if not view:
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            self._give_head()
            if "deco" in view:
                self.wfile.write(bytes(f'<h2>{http.s.server_name}</h2>\n', 'utf-8'))
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            if "env" in view:
                self._give_env()
            if "sys" in view:
                self._give_sys()
            if "gpio" in view:
                self.wfile.write(bytes(self._give_pins(), 'utf-8'))
            if "links" in view:
                self._give_links()
            self.wfile.write(bytes('</table>\n', 'utf-8'))
            if "log" in view:
                self.wfile.write(bytes(self._give_log(), 'utf-8'))
                if "deco" in view:
                    self.wfile.write(bytes(self._give_datetime(), 'utf-8'))
                self._give_foot(refresh = 60, scroll = True)
            else:
                if "deco" in view:
                    self.wfile.write(bytes(self._give_datetime(), 'utf-8'))
                self._give_foot(refresh = 60)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at "/" and "/graphs"')

    def do_HEAD(self):
        self._set_headers()
