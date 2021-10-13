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
from rrd import rrd

def ServeHTTP(s, rrd, haveScreen, haveSensor, env, sys, pin, toggleButton):
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
    http.haveScreen = haveScreen
    http.haveSensor = haveSensor
    http.sys = sys
    http.env = env
    http.pin = pin
    http.toggleButton = toggleButton
    # Start the server
    threadlog("HTTP server will bind to port " + str(s.port) + " on host " + s.host)
    httpd.server_bind()
    address = "http://%s:%d" % (httpd.server_name, httpd.server_port)
    threadlog("Access via: " + address)
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
    logging.info("[" + current_thread().name + "] : " + logline)

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

    def _give_head(self, titleExtra=""):
        title = http.s.serverName
        if (len(titleExtra) > 0):
            title= http.s.serverName +" :: " + titleExtra
        self.wfile.write(bytes('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n', 'utf-8'))
        self.wfile.write(bytes('<meta name="viewport" content="width=device-width,initial-scale=1">\n', 'utf-8'))
        self.wfile.write(bytes('<title>%s</title>\n' % title, 'utf-8'))
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
            if (scroll):
                self.wfile.write(bytes('function down() {\n', 'utf-8'))
                self.wfile.write(bytes('    window.scrollTo(0,document.body.scrollHeight);\n', 'utf-8'))
                self.wfile.write(bytes('    console.log("SCROLL" + document.body.scrollHeight);\n', 'utf-8'))
                self.wfile.write(bytes('}\n', 'utf-8'))
                self.wfile.write(bytes('window.onload = down;\n', 'utf-8'))
            if (refresh > 0):
                self.wfile.write(bytes('setTimeout(function(){location.replace(document.URL);}, ' + str(refresh*1000) + ');\n', 'utf-8'))
            self.wfile.write(bytes('</script>\n', 'utf-8'))
            self.wfile.write(bytes('</html>\n', 'utf-8'))

    def _give_datetime(self):
        timestamp = datetime.datetime.now()
        self.wfile.write(bytes('<div style="color:#666666; font-size: 90%; padding-top: 0.5em;">' + timestamp.strftime("%H:%M:%S, %A, %d %B, %Y") + '</div>\n', 'utf-8'))

    def _give_env(self):
        if http.haveSensor:
            # room sensors
            self.wfile.write(bytes('<tr><th>Room</th></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Temperature: </td><td>' + format(http.env['temperature'], '.1f') + '&deg;</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Humidity: </td><td>' + format(http.env['humidity'], '.1f') + '%</td></tr>\n', 'utf-8'))
            self.wfile.write(bytes('<tr><td>Presssure: </td><td>' + format(http.env['pressure'], '.0f') + 'mb</td></tr>\n', 'utf-8'))

    def _give_sys(self):
        # Internal Sensors
        self.wfile.write(bytes('<tr><th>Server</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Temperature: </td><td>' + format(http.sys['temperature'], '.1f') + '&deg;</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>CPU Load: </td><td>' + format(http.sys['load'], '1.2f') + '</td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>Memory used: </td><td>' + format(http.sys['memory'], '.1f') + '%</td></tr>\n', 'utf-8'))

    def _give_pins(self):
        # GPIO states
        if (len(http.s.pinMap) > 0):
            self.wfile.write(bytes('<tr><th>GPIO</th></tr>\n', 'utf-8'))
            for p in range(len(http.s.pinMap)):
                if (http.pin[p]):
                    self.wfile.write(bytes('<tr><td>' + http.s.pinMap[p][0] +'</td><td>on</td></tr>\n', 'utf-8'))
                else:
                    self.wfile.write(bytes('<tr><td>' + http.s.pinMap[p][0] +'</td><td>off</td></tr>\n', 'utf-8'))

    def _give_graphlinks(self, skip=""):
        if (len(skip) == 0):
            self.wfile.write(bytes('<tr><th>Graphs:</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr>', 'utf-8'))
        self.wfile.write(bytes('<td colspan="2" style="text-align: center;">', 'utf-8'))
        for g in http.s.graphDefaults:
            if (g != skip):
                self.wfile.write(bytes('&nbsp;<a href="./graphs?duration=' + g + '">' + g + '</a>&nbsp;', 'utf-8'))
            else:
                self.wfile.write(bytes('&nbsp;<span style="color: #AAAAAA;">' + g + '</span>&nbsp;', 'utf-8'))
        self.wfile.write(bytes('</td>', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))

    def _give_links(self):
        self._give_graphlinks()
        self.wfile.write(bytes('<tr>', 'utf-8'))
        self.wfile.write(bytes('<td colspan="2" style="text-align: center;"><a href="./?view=deco&view=env&view=sys&view=gpio&view=links&view=log">Inline Log</a>&nbsp;', 'utf-8'))
        self.wfile.write(bytes('&nbsp;<a href="./?view=deco&view=log&lines=' + str(http.s.logLines) + '">Main Log</a></td>', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))

    def _give_homelink(self):
        self.wfile.write(bytes('<tr>\n', 'utf-8'))
        self.wfile.write(bytes('<td colspan="2" style="text-align: center;"><a href="./">Home</a></td>\n', 'utf-8'))
        self.wfile.write(bytes('</tr>\n', 'utf-8'))

    def _give_log(self, lines=10):
        parsedLines = parse_qs(urlparse(self.path).query).get('lines', None)
        if (parsedLines):
            lines = parsedLines[0]
        # LogCmd is a shell one-liner used to extract the last {lines} of data from the logs
        # There is doubtless a more 'python' way to do this, but it is fast, cheap and works..
        logCmd = f"for a in `ls -tr {http.s.logFile}*`;do cat $a ; done | tail -{lines}"
        log = subprocess.check_output(logCmd, shell=True).decode('utf-8')
        self.wfile.write(bytes('<div style="overflow-x: auto; width: 100%;">\n', 'utf-8'))
        self.wfile.write(bytes('<span style="font-size: 110%; font-weight: bold;">Recent log activity:</span>\n', 'utf-8'))
        self.wfile.write(bytes('<hr><pre>\n' + log + '</pre><hr>\n', 'utf-8'))
        self.wfile.write(bytes(f'Latest {lines} lines shown\n', 'utf-8'))
        self.wfile.write(bytes('</div>\n', 'utf-8'))

    def _give_graphs(self, d):
        if http.haveSensor:
            allgraphs = [["env-temp","Temperature"],
                         ["env-humi","Humidity"],
                         ["env-pres","Pressure"],
                         ["sys-temp","CPU Temperature"],
                         ["sys-load","CPU Load Average"],
                         ["sys-mem","System Memory Use"]]
        else:
            allgraphs = [["sys-temp","CPU Temperature"],
                         ["sys-load","CPU Load Average"],
                         ["sys-mem","System Memory Use"]]
        for p in http.s.pinMap:
            allgraphs.append(["pin-" + p[0],p[0] + " GPIO"])
        self.wfile.write(bytes('<table>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><th>Graphs: -' + d + ' -> now</th></tr>\n', 'utf-8'))
        self.wfile.write(bytes('<tr><td>\n', 'utf-8'))
        for [g,t] in allgraphs:
            self.wfile.write(bytes('<tr><td><a href="graph?graph=' + g + '&duration=' + d + '">', 'utf-8'))
            self.wfile.write(bytes('<img title="' + t + '" src="graph?graph=' + g + '&duration=' + d + '">', 'utf-8'))
            self.wfile.write(bytes('</a></td></tr>\n', 'utf-8'))
        self.wfile.write(bytes('</td></tr>\n', 'utf-8'))
        self._give_graphlinks(skip=d)
        self._give_homelink()
        self.wfile.write(bytes('</table>\n', 'utf-8'))

    def do_GET(self):
        # Process requests and parse their options
        if (urlparse(self.path).path == '/graph'):
            parsedGraph = parse_qs(urlparse(self.path).query).get('graph', None)
            parsedDuration = parse_qs(urlparse(self.path).query).get('duration', None)
            if (not parsedGraph):
                body = ""
            elif (not parsedDuration):
                body = ""
            else:
                graph = parsedGraph[0]
                duration = parsedDuration[0]
                body = rrd.drawGraph(http.rrd, duration, graph, http.s.graphWide, http.s.graphHigh, http.s.areaC, http.s.areaW, http.s.lineC, http.s.lineW, http.s.serverName)
            if (len(body) == 0):
                self.send_error(404, 'Graph unavailable', 'Check your parameters and try again, see the "/graphs/" page for examples.')
                return
            self._set_png_headers()
            self.wfile.write(body)
        elif (urlparse(self.path).path == '/graphs'):
            parsed = parse_qs(urlparse(self.path).query).get('duration', None)
            if (not parsed):
                duration = "1d"
            else:
                duration = parsed[0]
            # logging.info('Graph Page (-' + duration + ' -> now) requested by: ' + self.client_address[0])
            self._set_headers()
            self._give_head(http.s.serverName + ":: graphs -" + duration)
            self.wfile.write(bytes('<h2>%s</h2>' % http.s.serverName, 'utf-8')) 
            self._give_graphs(duration)
            self._give_datetime()
            self._give_foot(refresh=300)
        elif ((urlparse(self.path).path == '/' + http.s.buttonPath) and (len(http.s.buttonPath) > 0)):
            parsed = parse_qs(urlparse(self.path).query).get('state', None)
            if (not parsed):
                action = 'toggle'
            else:
                action = parsed[0]
            logging.info('Web button triggered by: ' + self.client_address[0] + ' with action: ' + action)
            state = http.toggleButton(action)
            self._set_headers()
            self._give_head(http.s.serverName + ":: " + http.s.pinMap[0][0])
            self.wfile.write(bytes('<h2>' + state + '</h2>\n', 'utf-8'))
            self._give_datetime()
            self._give_foot()
        elif(urlparse(self.path).path == '/'):
            view = parse_qs(urlparse(self.path).query).get('view', None)
            if (not view):
                view = ["deco", "env", "sys", "gpio", "links"]
            self._set_headers()
            self._give_head()
            if "deco" in view: self.wfile.write(bytes('<h2>%s</h2>\n' % http.s.serverName, 'utf-8'))
            self.wfile.write(bytes('<table>\n', 'utf-8'))
            if "env" in view: self._give_env()
            if "sys" in view: self._give_sys()
            if "gpio" in view: self._give_pins()
            if "links" in view: self._give_links()
            self.wfile.write(bytes('</table>\n', 'utf-8'))
            if "log" in view:
                self._give_log()
                self._give_homelink()
                if "deco" in view:
                    self._give_datetime()
                self._give_foot(refresh = 60, scroll = True) 
            else:
                if "deco" in view:
                    self._give_datetime()
                self._give_foot(refresh = 60)
        else:
            self.send_error(404, 'No Such Page', 'This site serves pages at "/" and "/graphs"')

    def do_HEAD(self):
        self._set_headers()
