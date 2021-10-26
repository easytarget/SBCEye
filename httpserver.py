# Provides the http handler and request server for the Pi OverWatch

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
            title = f"{http.s.server_name}{title_extra}"
        return f'''
                <!DOCTYPE html>
                <html>
                <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>{title}</title>
                <style>
                body {{display:flex; flex-direction: column; align-items: center;}}
                a {{color:#666666; text-decoration: none;}}
                img {{width:auto; max-width:100%;}}
                table {{border-spacing: 0.2em; width:auto; max-width:100%;}}
                th {{font-size: 110%; text-align: left;}}
                td {{padding-left: 1em;}}
                </style>
                </head>
                <body>'''

    def _give_foot(self,scroll = False, refresh = 0):
        # DEBUG: self.wfile.write(bytes('<pre style="color:#888888">GET: ' + self.path + ' from: ' + self.client_address[0] + '</pre>\n', 'utf-8'))
        ret = '''</body>\n
                <script>\n'''
        if scroll:
            ret += '''function down() {
                        window.scrollTo(0,document.body.scrollHeight);
                        console.log("SCROLL" + document.body.scrollHeight);
                    }
                    window.onload = down;'''
        if refresh > 0:
            ret += f'setTimeout(function(){{location.replace(document.URL);}}, {str(refresh*1000)});\n'
        ret += '''</script>
                </html>'''
        return ret

    def _give_datetime(self):
        timestamp = datetime.datetime.now().strftime(http.s.time_format)
        return  f'''<div style="color:#666666;
                font-size: 90%; padding-top: 0.5em;">{timestamp}</div>
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
            ret += f'<tr><th>{http.s.sensor_name}</th></tr>\n'
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
        pinlist = {}
        for key in http.data.keys():
            if key[0:4] == 'pin-':
                pinlist[key] = key[4:]
        if len(http.data.keys() & pinlist.keys()) > 0:
            ret = '<tr><th>GPIO</th></tr>\n'
            for sense,name in pinlist.items():
                ret += f'<tr><td>{name}:</td><td>'\
                       f'{http.s.pin_states[bool(http.data[sense])]}</td></tr>\n'
        return ret

    def _give_graphlinks(self, skip=""):
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
                    ret += f'&nbsp;<span style="color: #AAAAAA;">{duration}</span>&nbsp;\n'
            if len(skip) > 0:
                ret += '&nbsp;:&nbsp;&nbsp;<a href="./" title="Main page">Home</a>\n'
            ret += '</td></tr>\n'
        return ret

    def _give_links(self):
        return f'''{self._give_graphlinks()}
                <tr>
                <td colspan="2" style="text-align: center;">
                <a href="./?view=deco&view=log" title="Open the log in a new page" target="_blank">
                Main Log</a>
                </td>
                </tr>'''

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
                        'Check your parameters and try again, see the "/graphs/" page for examples.')
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
            period = http.rrd.get_period(start, end)
            response = ''
            self._set_headers()
            response += self._give_head(f" :: graphs {period}")
            response += f'<h2>{http.s.server_name}</h2>'
            response += self._give_graphs(start, end, period)
            response += self._give_datetime()
            response += self._give_foot(refresh=300)
            self._write_dedented(response)
        elif ((urlparse(self.path).path == '/' + http.s.button_url)
                and (len(http.s.button_url) > 0)
                and (len(http.s.pin_map.keys()) > 0)):
            # Web Button
            response = ''
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if parsed:
                action = parsed[0]
            elif urlparse(self.path).query:
                self.send_error(404, 'Unknown Parameters',
                        'This URL takes a single parameter: "?state=<new state>"')
                return
            else:
                action = 'toggle'
            logging.info(f'Web button triggered by: {self.client_address[0]}'\
                    'with action: {action}')
            state = http.toggle_button(action)
            self._set_headers()
            response += self._give_head(f" :: {next(iter(http.s.pin_map))}")
            response += f'<h2>{state}</h2>\n'
            response += '<div><a href="./" title="Main page">Home</a></div>\n'
            response += self._give_datetime()
            response += self._give_foot()
            self._write_dedented(response)
        elif urlparse(self.path).path == '/':
            response = ''
            # Main Page
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if not view:
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            response += self._give_head()
            if "deco" in view:
                response += f'<h2>{http.s.server_name}</h2>\n'
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
                if "deco" in view:
                    response += self._give_datetime()
                response += self._give_foot(refresh = 60, scroll = True)
            else:
                if "deco" in view:
                    response += self._give_datetime()
                response += self._give_foot(refresh = 60)
            self._write_dedented(response)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at "/" and "/graphs"')

    def do_HEAD(self):
        self._set_headers()
