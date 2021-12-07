''' Functions to ping network targets and return their status

provides:
    Netreader: A class to handle overwatch net tests
    ping_target(host,timeout): test an individual target with a ping
'''
from subprocess import check_output, CalledProcessError, TimeoutExpired, PIPE
import threading
from time import sleep, time
import logging

class Netreader:
    '''Read and update networ ping status

    Runs a ping based network connectivity test based on the entries in a dictionary
    Updates the relevant entries in data{} and logs state changes

    parameters:
        settings: (tuple) consisting of:
            map: (dict) UI name and IP address/name
            timeout: (int) Timout in seconds
        data: the main data{} dictionary, a key/value pair; 'net-<name>=value'
            will be added to it and the vaue updated with pin state changes.

    provides:
        update_pins(): processes and updates the pins
    '''
    def __init__(self, settings, data):
        '''Setup and do initial reading'''
        (self.map, self.timeout) = settings
        self.states = {}
        if not self.map:
            print('No network addresses configured for monitoring')
            return
        for name,_ in self.map.items():
            self.states[name] = "init"
        self.update(data)
        print('Network monitoring configured and logging enabled')
        logging.info('Network monitoring configured and logging enabled')

    def _ping_runner(self, target, data):
        '''Invokes ping_target() and waits for a return
        updates the data{} dict and emits logs on status changes
        - Intended to be run in parallel threads
        parameters:
            target: name of the remote machine to be pinged
            data: the main data{} dictionary
        no return
        '''
        address = self.map[target]
        key = f'net-{target}'
        (data[key], status) = ping_target(address,self.timeout)
        if status:
            if status != self.states[target]:
                # Log new failure state
                logging.info(f'Ping fail: {target} ({address}): {status}')
                self.states[target] = status
        else:
            if self.states[target]:
                # Log now responding
                logging.info(f'Ping ok: {target} ({address}) in {data[key]:.1f}ms')
                self.states[target] = None

    def update(self, data):
        '''Test each target in parallel via threads'''
        threadlist = []
        for target,_ in self.map.items():
            gatherer = threading.Thread(target=self._ping_runner, args=[target, data])
            gatherer.start()
            threadlist.append(gatherer)
        # Now wait till all the threads we started have terminated
        start = time()
        while set(threadlist) & set(threading.enumerate()):
            sleep(0.1)
            if time() > start + (self.timeout * 2):
                threadlist = []
                logging.warning('PING Lockup! this should not happen, '\
                        'may leave zombie threads and processes.')

def ping_target(address, timeout):
    '''Returns the ping/connectivity status for a target

    parameters:
        address: (str) target IP/Name to ping
        timeout: (int) Timeout for command in seconds

    returns:
        time_data: (int) response time in miliseconds or (str) 'U' if failing
        err: (str) Error string for fail situations, or None
    '''
    time_data = 'U'
    err_txt = None
    try:
        ping_return = check_output(['ping', '-c', '1', address],
                stderr=PIPE, timeout=timeout)
    except CalledProcessError as pingerror:
        if pingerror.returncode == 1:
            err_txt = f'Unreachable:: {pingerror.stdout.decode("utf-8").split(chr(10))[1]}'
        elif pingerror.returncode == 2:
            err_txt = f'Error:: {pingerror.stderr.decode("utf-8").split(chr(10))[0]}'
        else:
            err_txt = f'Unexpected Error ({pingerror.returncode}):: see debug'
            print(f'{pingerror.stderr.decode("utf-8")}')
    except TimeoutExpired:
        err_txt = f'Timeout:: {timeout*1000:.0f}ms'
    else:
        # success, extract the time from the command return
        line1 = str(ping_return.decode('utf-8').split('\n')[1])
        time_string= next(x for x in line1.split(' ') if x[:5] == 'time=')
        time_data = float(time_string[5:])
    return time_data, err_txt
