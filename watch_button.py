# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
import gpiod
from datetime import timedelta

INPUT = gpiod.line.Direction.INPUT
RISING_EDGE = gpiod.edge_event.EdgeEvent.Type.RISING_EDGE
FALLING_EDGE = gpiod.edge_event.EdgeEvent.Type.FALLING_EDGE

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
class buttonHandler:
    class _button:
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
                event():
                    blocks and waits for events
                    returns a string with 'rising' or 'falling' otherwise
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
                                            direction=INPUT,
                                            bias=bias,
                                            edge_detection=edge,
                                            event_clock=clock,
                                            debounce_period=debounce)})
            if self.verbose:
                print('Configured: \'{}\':{} as input (locked)'
                    .format(self.chip, self.line))

        def release(self):
            self.request.release()
            print('Released lock on input: \'{}\':{}'.format(self.chip, self.line))

        def event(self):
            self.request.wait_edge_events(timeout=None):
            event = self.request.read_edge_events(max_events=1)[0]
            if event.line_offset == self.line:
                if event.event_type == RISING_EDGE:
                    return 'rising'
                elif event.event_type == FALLING_EDGE:
                    return 'falling'

    def __init__(self, settings, gpio):
        # take settings (and gpio object to flip value)
        # start a thread for each watched button
        pass
