import gpiod

from os import getpid
from time import sleep, asctime
from datetime import timedelta
from re import search

# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
if int(search('^[0-9]+', gpiod.__version__).group(0)) < 2:
    raise ImportError('gpiod bindings library version too low ({}), '\
                      'pinreader requires gpiod v2.x.x or later.'
                      .format(gpiod.__version__))

def get_device(chip, line):
        ''' Common gpiochip+line setup '''
        # Test whether chip is a gpiochip
        if not gpiod.is_gpiochip_device(chip):
            raise ValueError('Not a gpiochip device: \'{}\''.format(chip))
        # Test we can use gpiochip
        try:
            device = gpiod.Chip(chip)
        except Exception as e:
            raise ValueError('Failed to setup gpiochip (\'{}\') device:\n{}'
                  .format(chip, e))
        # Test if the line is already used by another consumer
        if device.get_line_info(line).used:
            raise ValueError('Cannot acquire gpiochip \'{}\' line {}, '\
                             'currently used by: \'{}\''
                  .format(line,  device.get_line_info(self.line).consumer))
        return device

# Input
class input_pin:
    '''
        Sets the input pin up to monitor for changes:
        - pin will be used (consumed) by the process
        Takes:
            chip  (str)
            line (int)
            consumer (string)
            verbose (bool)
        Provides:
            event(timeout):
                blocks and waits for events
                returns None if no event within timeout
                returns a string with 'rising' or 'falling' otherwise
                timeout = a timedelta object or
                          0 for immediate return or
                          None to wait indefinately
    '''
    def __init__(self, chip, line, consumer, verbose=False):
        self.chip = chip
        self.line = line
        self.consumer = consumer
        self.bias = gpiod.line.Bias.DISABLED
        self.edge = gpiod.line.Edge.BOTH
        self.clock = gpiod.line.Clock.MONOTONIC
        self.debounce = 100
        self.verbose = verbose
        self.states = (gpiod.line.Value.INACTIVE, gpiod.line.Value.ACTIVE)
        # Get and test the device
        self.device = get_device(self.chip, self.line)
        # Create a request object for the input
        self.request = self.device.request_lines(
                            consumer=self.consumer,
                            config={self.line: gpiod.LineSettings(
                                        direction=gpiod.line.Direction.INPUT,
                                        bias=self.bias,
                                        edge_detection=self.edge,
                                        event_clock=self.clock,
                                        debounce_period=timedelta(milliseconds=self.debounce))})
        if self.verbose:
            print('Configured: \'{}\':{} as input'
                .format(self.chip, self.line))

    def event(self, timeout=0):
        if self.request.wait_edge_events(timeout=timeout):
            events =  self.request.read_edge_events()
            for event in events:
                if event.line_offset == self.line:
                    if event.event_type == gpiod.edge_event.EdgeEvent.Type.RISING_EDGE:
                        return 'rising'
                    elif event.event_type == gpiod.edge_event.EdgeEvent.Type.FALLING_EDGE:
                        return 'falling'
        return None

# Output
class output_pin:
    '''
        Sets the output pin up:
        Takes:
            chip  (str)
            line (int)
            consumer (string)
            lock (bool)
            verbose (bool)
        Provides:
            set(value): sets the output value (int: 0 or 1)
            get():      gets the output value (int: 0 or 1)
    '''
    def __init__(self, chip, line, consumer, lock=False, verbose=False):
        self.chip = chip
        self.line = line
        self.consumer = consumer
        self.verbose = verbose
        self.states = (gpiod.line.Value.INACTIVE, gpiod.line.Value.ACTIVE)
        # Get and test the device
        self.device = get_device(self.chip, self.line)
        # Create a request object if we are a consumer, otherwise None
        if lock:
            self.request = self.device.request_lines(consumer=self.consumer,
                                config={self.line: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)})
        else:
            self.request = None
        if self.verbose:
            print('Configured: \'{}\':{} as output ({})'
                .format(self.chip, self.line, 'locked' if lock else 'unlocked'))

    def get(self):
        if self.request:
            value = self.states.index(self.request.get_value(self.line))
        else:
            with self.device.request_lines(
                    consumer=self.consumer,
                    config={self.line: None},
                    ) as line:
                value = self.states.index(line.get_value(self.line))
        return value

    def set(self, value):
        if self.request:
            self.request.set_value(self.line, self.states[value])
        else:
            with self.device.request_lines(
                    consumer=self.consumer,
                    config={self.line: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)},
                    ) as line:
                line.set_value(self.line, self.states[value])

# HTTP server
import http.server
from urllib.parse import urlparse
from threading import Thread

def serve_http(out, host='0.0.0.0', port=7090, off='off', on='on', toggle='toggle', debug=True):
    '''Spawns a http.server.HTTPServer in a separate thread on the given port'''
    handler = _BaseRequestHandler
    httpd = http.server.ThreadingHTTPServer((host, port), handler, False)
    httpd.timeout = 0.5
    httpd.allow_reuse_address = True
    # Storing attributes in the http class itself is cheeky, but simple and effective.
    http.out = out
    http.host = host
    http.port = port
    http.states = (off, on)
    http.toggle = toggle
    http.debug = debug
    # Start the server
    httpd.server_bind()
    http.address = f"http://{httpd.server_name}:{httpd.server_port}"
    print(f"http server: {http.address}",flush=True)
    # Serve requests using threads
    httpd.server_activate()
    def serve_forever(httpd):
        with httpd:
            httpd.serve_forever()
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.daemon = True
    thread.start()

class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # This function suppresses the http server log output
        if http.debug:
            print(f'HTTP request:: {self.client_address[0]} : {args[0]} '\
                  f'({args[1]})',flush=True)
        return

    def do_GET(self):
        '''Process requests and parse their options'''
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        if urlparse(self.path).path == '/{}'.format(http.states[0]):
            http.out.set(0)
        elif urlparse(self.path).path == '/{}'.format(http.states[1]):
            http.out.set(1)
        elif urlparse(self.path).path == '/{}'.format(http.toggle):
            http.out.set(1 - http.out.get())
        elif urlparse(self.path).path == '/':
            pass
        else:
            self.send_error(404, 'No Match', 'Nothing matches the URL')
            return
        self.wfile.write(bytes(http.states[http.out.get()], 'utf-8'))

# Main
if __name__ == '__main__':
    from sys import argv
    # demo
    output_chip = '/dev/gpiochip0'
    output_line = 7
    button_chip = '/dev/gpiochip0'
    button_line = 27

    consumer = '{}-{}'.format(argv[0], getpid())
    out = output_pin(output_chip, output_line, consumer, lock=False)
    button = input_pin(button_chip, button_line, consumer)
    looptime = timedelta(seconds=60)

    def flip():
        current = out.get()
        if current == 0:
            out.set(1)
            return('lamp on')
        else:
            out.set(0)
            return('lamp off')

    print('running: {}'.format(argv[0]))

    serve_http(out)

    while True:
        ev = button.event(timeout=looptime)
        if ev == 'rising':
            print('{} : {}'.format(asctime(), flip()), flush=True)
