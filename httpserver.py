'''Provides the threaded http handler for the SBCEye project
'''

# pragma pylint: disable=logging-fstring-interpolation,no-self-use

import sys
import os.path
import time
from subprocess import check_output
import re

# HTTP server
import http.server
from urllib.parse import urlparse, parse_qs
from threading import Thread

# Logging
import logging

def serve_http(settings, rrd, gpio, data):
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
    http.gpio = gpio
    http.data = data
    http.icon_file = 'favicon.ico'
    if not os.path.exists(http.icon_file):
        http.icon_file = f'{sys.path[0]}/{http.icon_file}'
    if rrd.rrdtool and rrd.gzip:
        http.db_graphable = True
        if settings.web_allow_dump:
            logging.info("RRD database is dumpable via web")
            http.db_dumpable = True
        else:
            http.db_dumpable = False
        if settings.web_allow_backup:
            logging.info("RRD database backups can be triggered via web")
            http.db_backupable = True
        else:
            http.db_backupable = False
    else:
        logging.warning('Commandline rrdtool or gzip not found, '\
                'graphing, backup and dumping functions are unavailable')
        http.db_dumpable = False
        http.db_graphable = False

    # Note the list of link targets
    for link in settings.links:
        logging.info(f"Web link '{link}' points to: {settings.links[link]}")

    # Note the controllable pins
    for pin in settings.outpins:
        logging.info(f"Pin '{pin}' controllable via web ui")

    # Start the server
    logging.info(f'HTTP server will bind to port {str(settings.web_port)} '\
            f'on host {settings.web_host}')
    httpd.server_bind()
    address = f"http://{httpd.server_name}:{httpd.server_port}"
    print(f"Webserver starting on : {address}",flush=True)
    httpd.server_activate()

    def serve_forever(httpd):
        with httpd:  # to make sure httpd.server_close is called
            logging.info("Http Server starting")
            httpd.serve_forever()
            logging.info("Http Server closing down")

    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.daemon = True
    thread.start()


class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):
    '''Handles each individual request in a new thread'''

    def log_message(self, format, *args):
        # This function effectively suppresses the http server log output
        if http.settings.debug_http:
            print(f'HTTP request:: {self.client_address[0]} : {args[0]} '\
                  f'({args[1]})',flush=True)
        return


    def _common_headers(self):
        self.send_response(200)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')

    def _redirect(self):
        self._common_headers()
        self.send_header('refresh', '0; url=./')
        self.end_headers()

    def _set_headers(self):
        self._common_headers()
        self.send_header("Content-type", "text/html")
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
                a {{color:#000000; text-decoration: none;}}
                img {{width:auto; max-width:100%;}}
                table {{border-spacing-top: 0.4em; width:auto; max-width:100%;}}
                th {{font-size: 110%; text-align: left;}}
                td {{padding-left: 1em; padding-right: 0;}}
                </style>
                </head>
                <body>'''

    def _give_foot(self, refresh=0, scroll=False):
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
                <div style="color:#555555;
                font-size: 66%; font-weight: lighter; padding-top:0.5em">
                <a style="color:#555555;"
                href="https://github.com/easytarget/SBCEye"
                title="Project homepage on GitHub" target="_blank">
                SBCEye</a></div>'''

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
                            f'{http.data[sense]:{fmt}}</td>'\
                            f'<td style="padding-left: 0;">{suffix}</td></tr>\n'
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
                            f'{http.data[sense]:{fmt}}</td>'\
                            f'<td style="padding-left: 0;">{suffix}</td></tr>\n'
        return ret

    def _give_net(self):
        # Network Connectivity
        ret = ''
        targetlist = {}
        for key in http.data.keys():
            if key[0:4] == 'net-':
                targetlist[key] = key[4:]
        if len(http.data.keys() & targetlist.keys()) > 0:
            ret += '<tr><th>Ping</th></tr>\n'
            for item,name in targetlist.items():
                ret += f'<tr><td title="{http.settings.netlist[name]}">{name}:</td>'
                if http.data[item] == 'U':
                    ret += '<td style="text-align: right;">Fail</td></tr>\n'
                else:
                    ret += f'<td style="text-align: right;">{http.data[item]:.1f}</td>'\
                            '<td style="padding-left: 0;">'\
                            '<span style="font-size: 75%;"> ms</span>'\
                            '</td></tr>\n'
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
            for item, name in pinlist.items():
                title = '{}:\n chip: {}\n line: {}\n direction: {}\n consumer: {}'.format(
                            name, http.gpio.pins[name].chip, http.gpio.pins[name].line,
                            http.gpio.pins[name].direction, http.gpio.pins[name].consumer)
                ret += f'<tr><td title="{title}">{name}:</td>'
                direction = '({})'.format(http.gpio.pins[name].direction[:-3])
                consumer = '{}'.format(http.gpio.pins[name].consumer)
                if http.data[item] == 'U':
                    ret += '<td style="text-align: right;"><span style="font-size: 80%; '\
                           'font-style: italic;">{}</span></td>'.format(consumer)
                    direction = ''
                else:
                    em = 'font-weight: bold' if http.data[item] == 1 else ''
                    if name in http.settings.outpins:
                        link = 'href="./{}" title="Pin Control" '\
                               'style="text-decoration: underline; {}"'.format(name, em)
                        ret += '<td style="text-align: right;"><a {}>{}</a></td>'\
                                .format(link, http.settings.pin_state_names[http.data[item]])
                    else:
                        ret += '<td style="text-align: right;"><span style="{}">{}</span></td>'\
                                .format(em, http.settings.pin_state_names[http.data[item]])
                ret += '<td style="padding-left: 0.3em;"><span style="font-size: 75%;">'\
                       '{}</span></td></tr>\n'.format(direction)
        return ret

    def _give_graphlinks(self, skip=""):
        # A list of available graph pages
        ret = ''
        skip = skip.lstrip('end-')
        if (len(http.settings.graph_durations) > 0) and http.db_graphable:
            if len(skip) == 0:
                ret += '<tr><th>Graphs</th></tr>\n'
            ret += '<tr><td colspan="3" style="text-align: center; font-size: 86%;">\n'
            for duration in http.settings.graph_durations:
                if duration != skip:
                    ret += f'<a href="./graphs?start=end-{duration}" '\
                           f'title="Graphs covering the last {duration} in time">'\
                           f'{duration}</a>&nbsp;\n'
                else:
                    ret += f'<span style="color: #BBBBBB;">{duration}</span>&nbsp;\n'
            if len(skip) > 0:
                ret += '</td></tr>\n<tr><td colspan="2" style="text-align: center">'\
                       '<a href="./" title="Main page">Home</a>\n'
            ret += '</td></tr>\n'
        return ret

    def _give_links(self):
        # Links to the graph pages
        ret = f'{self._give_graphlinks()}'
        # Configured links and log page
        for link in http.settings.links:
            ret += f'<tr><td colspan="3" style="text-align: center">'\
                   f'<a href="{http.settings.links[link]}" title="Open {link} in a new tab" target="_blank">'\
                   f'{link}</a></td></tr>\n'
        ret += f'<tr><td colspan="3" style="text-align: center">\n'\
               f'<a href="./log" title="Open log in a new tab" target="_blank">'\
               f'Action Log</a></td></tr>\n'
        return ret

    def _give_log(self, lines=32):
        # Combine and give last (lines) lines of log
        parsed_lines = parse_qs(urlparse(self.path).query).get('lines', None)
        if isinstance(parsed_lines, list):
            lines = parsed_lines[0]
        # Do not pass anything other than integers to the shell commsnd..
        if not isinstance(lines, int):
            try:
                lines = int(lines)
            except ValueError:
                lines = int(32)
        lines = max(1, lines)
        # Use a shell one-liner used to extract the last {lines} of data from the logs
        # There is doubtless a more 'python' way to do this, but it is fast, cheap and works..
        log_command = \
            f"for a in `ls -tr {http.settings.log_file}*`;do cat $a ; done | tail -{lines}"
        log = check_output(log_command, shell=True).decode('utf-8')
        ret = f'''
                <div style="overflow-x: auto; width: 100%;">\n
                <span style="font-size: 110%; font-weight: bold;">Recent log activity:</span>
                <hr><pre>\n{log}</pre><hr>
                <span style="font-size: 80%;">Latest {lines} lines shown</span>\n
                </div>\n
                <div><a href="./log?lines=32" title="show 32 lines">32</a>&nbsp;:
                <a href="./log?lines=320" title="show 320 lines">320</a>&nbsp;:
                <a href="./log?lines=3200" title="show 3200 lines">3200</a></div>\n
                <div><a href="./" title="Main page">Home</a></div>\n'''
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
                Generating the dump imposes a high load on the SBCEye process and
                can potentially impact other software running on the system.
                <br>
                It can take several minutes to complete; depending on the
                host machine and db size+complexity. <em>Use with care!</em>
                <hr>
                If you are sure you wish to proceed:<br>
                <a href="./dump_gz" title = "Direct download link">Download</a>
                </div>
                '''

    def _give_pin_portal(self, pin):
        ret = f'<h2><a href="/" title="Home">{http.settings.name}</a> Pin Control</h2>\n'
        ret += f'<div style="font-size: 200%; ">{pin} : <span style="font-weight: bold">{http.settings.pin_state_names[http.gpio.pins[pin].value]}</span></div>\n'
        ret += '<div>Current mode: <span style="font-weight: bold">{}</span><hr></div>\n'.format(http.gpio.pins[pin].direction)
        ret += '<div><a href="?{0}" title="mode: output\nvalue: {0}">Set output: {0}</a></div>\n'.format(http.settings.pin_state_names[0], pin)
        ret += '<div><a href="?{0}" title="mode: output\nvalue: {0}">Set output: {0}</a></div>\n'.format(http.settings.pin_state_names[1], pin)
        ret += '<div><a href="?input" title="mode: input">Change mode to input and show value</a></div>\n'.format(pin)
        ret += '<div><br><a href="./" title="Main page">Home</a></div>\n'
        return ret

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
            response += f'<h2><a href="/">{http.settings.name}</a></h2>'
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
        elif (urlparse(self.path).path == '/dump_gz') and http.db_dumpable:
            # Raw dump download
            start = time.time()
            logging.info(f"RRD database dump requested by {self.client_address[0]}")
            response = http.rrd.dump(reason=f'Web ({self.client_address[0]})')
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
        elif (urlparse(self.path).path == '/backup') and http.db_backupable:
            # trigger a backup and notify
            logging.info(f"RRD database backup triggered by {self.client_address[0]}")
            self.send_response(302)
            self.send_header('Location','log')
            self.end_headers()
            http.rrd.backup()
        elif urlparse(self.path).path == '/log':
            self._set_headers()
            response = self._give_head(" :: Logfile Viewer")
            response += f'<h2><a href="/" title="Home">{http.settings.name}</a> Log</h2>\n'
            response += self._give_log()
            response += self._give_timestamp()
            response += self._give_foot(refresh=60, scroll=True)
            self._write_dedented(response)
        elif urlparse(self.path).path[1:] in  http.settings.outpins:
            pin = urlparse(self.path).path[1:]
            parsed_action = urlparse(self.path).query
            action = parsed_action.casefold()
            if action == http.settings.pin_state_names[0].casefold():
                http.gpio.setPin(pin, 0)
                self._redirect()
                logging.info('Pin \'{}\' set output: {} via web ({})'
                             .format(pin, http.settings.pin_state_names[0], self.client_address[0]))
                return
            elif action == http.settings.pin_state_names[1].casefold():
                http.gpio.setPin(pin, 1)
                self._redirect()
                logging.info('Pin \'{}\' set output: {} via web ({})'
                             .format(pin, http.settings.pin_state_names[1], self.client_address[0]))
                return
            elif action == 'input':
                http.gpio.makeInput(pin)
                self._redirect()
                logging.info('Pin \'{}\' set to input mode via web ({})'
                             .format(pin, self.client_address[0]))
                return
            elif parsed_action != '':
                self.send_error(418, 'I\'m a {}, '\
                    'I do not know how to \'{}\''\
                    .format(pin, parsed_action))
                return
            self._set_headers()
            response = self._give_head(" :: Pin Control :: {}".format(pin))
            response += self._give_pin_portal(pin)
            response += self._give_timestamp()
            response += self._give_foot(refresh=60)
            self._write_dedented(response)
        elif urlparse(self.path).path == '/':
            # Main Page
            exclude = parse_qs(urlparse(self.path).query).get('exclude', '')
            exclude = [item for sublist in exclude for item in sublist.split(',')]
            self._set_headers()
            response = self._give_head()
            if not "deco" in exclude:
                response += f'<h2>{http.settings.name}</h2>\n'
            response += '<table>\n'
            if not "env" in exclude:
                response += self._give_env()
            if not "sys" in exclude:
                response += self._give_sys()
            if not "net" in exclude:
                response += self._give_net()
            if not "gpio" in exclude:
                response += self._give_pins()
            if not "links" in exclude:
                response += self._give_links()
            response += '</table>\n'
            if not "deco" in exclude:
                response += self._give_timestamp()
            response += self._give_foot(refresh=60)
            self._write_dedented(response)
        else:
            self.send_error(404, 'No Such Page',
                    'Nothing matches the given URL on this server')

    def do_HEAD(self):
        '''returns headers'''
        self._set_headers()
