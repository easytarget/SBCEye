import gpiod
from os import getpid
from time import sleep, asctime
from datetime import timedelta
from re import search
from threading import Thread
import http.server
from urllib.parse import urlparse

# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
if int(search('^[0-9]+', gpiod.__version__).group(0)) < 2:
    raise ImportError('gpiod bindings library version too low ({}), '\
                      'pinreader requires gpiod v2.x.x or later.'
                      .format(gpiod.__version__))

def _get_device(chip, line):
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
            debounce (int) in ms
            verbose (bool)
        Provides:
            event(timeout):
                blocks and waits with timeout for events
                returns None if no event within timeout
                returns a string with 'rising' or 'falling' otherwise
                timeout = a timedelta object or
                          0 for immediate return or
                          None to wait indefinately
    '''
    def __init__(self, chip, line, consumer, debounce, verbose=False):
        self.chip = chip
        self.line = line
        bias = gpiod.line.Bias.AS_IS
        edge = gpiod.line.Edge.BOTH
        clock = gpiod.line.Clock.MONOTONIC
        debounce = timedelta(milliseconds=debounce)
        self.verbose = verbose
        # Get and test the device
        device = _get_device(self.chip, self.line)
        if device.get_line_info(line).used:
            raise ValueError('Cannot acquire gpiochip \'{}\' line {}, '\
                             'currently used by: \'{}\''
                  .format(chip, line, device.get_line_info(line).consumer))
        # Create a request object for the input
        self.request = device.request_lines(
                                consumer=consumer,
                                config={line: gpiod.LineSettings(
                                        direction=gpiod.line.Direction.INPUT,
                                        bias=bias,
                                        edge_detection=edge,
                                        event_clock=clock,
                                        debounce_period=debounce)})
        if self.verbose:
            print('Configured: \'{}\':{} as input (locked)'
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
            set(value): sets the output value (int: 0 or 1 for low/high)
                        returns True if successful, False if output is unavailable
            get():      gets the output value (int: 0, 1 or 2=unavailable)
    '''
    def __init__(self, chip, line, consumer, lock=False, verbose=False):
        self.chip = chip
        self.line = line
        self.consumer = consumer
        self.verbose = verbose
        self.states = (gpiod.line.Value.INACTIVE, gpiod.line.Value.ACTIVE)
        # Get and test the device
        self.device = _get_device(self.chip, self.line)
        # Create a request object as needed
        if lock:
            if self.device.get_line_info(line).used:
                raise ValueError('Cannot acquire gpiochip \'{}\' line {}, '\
                                 'currently used by: \'{}\''
                      .format(chip, line,  self.device.get_line_info(line).consumer))
            self.request = self.device.request_lines(consumer=self.consumer,
                            config={self.line: gpiod.LineSettings(
                                    direction=gpiod.line.Direction.OUTPUT)})
        else:
            self.request = None
        if self.verbose:
            print('Configured: \'{}\':{} as output ({})'
                .format(self.chip, self.line, 'locked' if lock else 'unlocked'))

    def get(self):
        if self.request:
            value = self.states.index(self.request.get_value(self.line))
        else:
            try:
                with self.device.request_lines(
                        consumer=self.consumer,
                        config={self.line: None},
                        ) as line:
                    value = self.states.index(line.get_value(self.line))
            except OSError:
               value = 2   # 2 = unavailable
        return value

    def set(self, value):
        if self.request:
            self.request.set_value(self.line, self.states[value])
        else:
            try:
                with self.device.request_lines(
                        consumer=self.consumer,
                        config={self.line: gpiod.LineSettings(
                                    direction=gpiod.line.Direction.OUTPUT)},
                        ) as line:
                    line.set_value(self.line, self.states[value])
            except OSError:
                return False
        return True

def _serve_http(out, host, port, states, toggle, portal, refresh, verbose, debug):
    '''Spawns a http.server.HTTPServer in a separate thread on the given port'''
    handler = _BaseRequestHandler
    httpd = http.server.ThreadingHTTPServer((host, port), handler, False)
    httpd.timeout = 0.5
    httpd.allow_reuse_address = True
    # Storing attributes in the http class itself is cheeky, but simple and effective.
    http.out = out
    http.states = states
    http.toggle = toggle
    http.portal = portal
    http.refresh = refresh
    http.verbose = verbose
    http.debug = debug
    http.lastknown = http.states[http.out.get()]
    # Start the server
    httpd.server_bind()
    http.address = f"http://{httpd.server_name}:{httpd.server_port}"
    if http.verbose:
        print(f"HTTP server: {http.address}",flush=True)
    # Serve requests using threads
    httpd.server_activate()
    def serve_forever(httpd):
        with httpd:
            httpd.serve_forever()
    thread = Thread(target=serve_forever, args=(httpd, ))
    thread.daemon = True
    thread.start()

''' Base request handler class for the http server '''
class _BaseRequestHandler(http.server.BaseHTTPRequestHandler):

    ''' suppress the http server log output '''
    def log_message(self, format, *args):
        if http.debug:
            print(f'DEBUG: HTTP request:: {self.client_address[0]} : {args[0]} '\
                  f'({args[1]})',flush=True)
        return

    ''' handle GET requests : this is where logic lives '''
    def do_GET(self):
        def common_headers():
            self.send_response(200)
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')

        def redirect():
            common_headers()
            self.send_header('refresh', '0; url=/')
            self.end_headers()

        def getval():
            # return current state and inverse
            cur = alt = http.out.get()
            if cur == 0:
                alt = 1
            elif cur == 1:
                alt = 0
            return cur, alt

        # parse request and process
        if urlparse(self.path).path == '/{}'.format(http.states[0]):
            http.out.set(0)
            redirect()
            return
        elif urlparse(self.path).path == '/{}'.format(http.states[1]):
            http.out.set(1)
            redirect()
            return
        elif urlparse(self.path).path == '/{}'.format(http.toggle):
            http.out.set(getval()[1])
            redirect()
            return
        elif urlparse(self.path).path != '/':
            self.send_error(404, 'No Match', 'Nothing matches the URL')
            return
        state, alt = getval()
        state = http.states[state]
        alt = http.states[alt]
        common_headers()
        self.send_header('refresh', '{}; url=/'.format(http.refresh))
        self.end_headers()
        self.wfile.write(bytes(http.portal.replace('__STATE__', state)\
                                          .replace('__ALT__', alt)\
                                          .replace('__NOW__', asctime()), 'utf-8'))
        # only log if value changed
        if state != http.lastknown and http.verbose:
            print('{} : http ({}) : {}'.format(asctime(), self.client_address[0], state))
        http.lastknown = state

''' The pinpopper class itself '''
class PinPopper:
    def __init__(self, outpin, inpin=None, web=None,
                 name='pinpopper',
                 states=('off', 'on', 'unavailable'),
                 toggle='toggle',
                 debounce=66,
                 edge='rising',
                 portal='__STATE__',
                 refresh=60,
                 lock=True,
                 verbose=True, debug=False):
        self._outpin = outpin
        self._inpin = inpin
        self._consumer = '{}-{}'.format(name, getpid())
        self._states = states
        self._toggle = toggle
        self.cmdlist = (states[0], states[1], toggle)
        self._verbose = verbose
        self._debug = debug
        # Acquire the output pin
        self._output = output_pin(outpin[0], outpin[1], self._consumer, lock, verbose)
        # If input is specified; acquire it and start input handler thread
        if self._inpin is not None:
            self._input = input_pin(inpin[0], inpin[1], self._consumer, debounce, verbose)
            inserve = Thread(target=self._serve_input, args=(edge, verbose, ))
            inserve.daemon = True
            inserve.start()
        # If http (host, port) is specified; start http server thread
        if web is not None:
            _serve_http(self._output, web[0], web[1],
                        states, toggle, portal, refresh, verbose, debug)
        # Show initial state as required
        if verbose:
            print('Initial output: {}'.format(states[self._output.get()]))
        else:
            print(states[self._output.get()])

    ''' A simple function to invert the output '''
    def _flip(self):
        current = self._output.get()
        if current == 0:
            self._output.set(1)
        elif current == 1:
            self._output.set(0)

    def _serve_input(self, edge, verbose):
        '''service loop serving the input pin events (run in a thread)'''
        while True:
            event = self._input.event(timeout=None)
            if event == edge:
                self._flip()
                if self._verbose:
                    print('{} : button : {}'.format(asctime(),
                        self._states[self._output.get()]), flush=True)

    def get(self):
        return self._states[self._output.get()]

    def set(self, action):
        if action == self._states[0]:
            self._output.set(0)
        elif action == self._states[1]:
            self._output.set(1)
        elif action == self._toggle:
            self._flip()
        else:
            # ignore invalid actions by default, unless debug is on.
            if self._debug:
                print('DEBUG: PinPopper: invalid action: \'{}\''.format(action))
        if self._verbose:
            print('{} : set(\'{}\') : output = {}'.format(asctime(), action,
                    self._states[self._output.get()]), flush=True)

# Main
if __name__ == '__main__':
    # demo
    from sys import argv, stdin

    output = ('/dev/gpiochip0', 7)
    button = ('/dev/gpiochip0', 27)
    web = ('0.0.0.0', 7090)
    name = 'Lamp'
    states = ('Low', 'High', 'N/A')
    toggle = 'Invert'
    portal = '<body style="text-align: center;"><div>__NOW__</div>'\
             '<h1>Lamp: __STATE__</h1><h3>'\
             '<a href="./__ALT__">switch: __ALT__</a></h3></body>'
    verbose = True

    popper = PinPopper(output, button, web, name, states, toggle, portal=portal, lock=False, verbose=verbose)

    if verbose:
        print('Available commands: {}'.format(popper.cmdlist + ('exit',)))
        print('Starting:: {}'.format(name))

    # Now loop forever passing stdin commands to pinpopper.set()
    with stdin as cmds:
        while True:
            cmd = cmds.readline().strip()
            if cmd in popper.cmdlist:
                popper.set(cmd)
            elif cmd in ('exit', 'quit', 'bye'):
                break
            elif cmd and verbose:
                print('{} : invalid action (\'{}\')'
                        .format(asctime(), cmd))
            print(popper.get())

