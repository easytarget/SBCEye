# Needs gpiod bindings at V2.0 or later, standard debian12/bookworm is v1.6
#  use a virtualenv and 'pip install --upgrade gpiod' as needed.
import gpiod
import logging
from datetime import timedelta
from threading import Thread
from os import getpid

INPUT = gpiod.line.Direction.INPUT
RISING_EDGE = gpiod.edge_event.EdgeEvent.Type.RISING_EDGE
FALLING_EDGE = gpiod.edge_event.EdgeEvent.Type.FALLING_EDGE

def _get_device(chip, line):
        ''' Common gpiochip+line setup '''
        # Test whether chip is a gpiochip
        if not gpiod.is_gpiochip_device(chip):
            raise ValueError('Button setup: Not a gpiochip device: \'{}\''.format(chip))
        # Test we can use gpiochip
        try:
            device = gpiod.Chip(chip)
        except Exception as e:
            raise ValueError('Button setup: Failed to setup gpiochip (\'{}\') device:\n{}'
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
            Provides:
                event():
                    blocks and waits for events
                    returns a string with 'rising' or 'falling' otherwise
        '''
        def __init__(self, chip, line, consumer, debounce):
            self.chip = chip
            self.line = line
            bias = gpiod.line.Bias.AS_IS
            edge = gpiod.line.Edge.BOTH
            clock = gpiod.line.Clock.MONOTONIC
            debounce = timedelta(milliseconds=debounce)
            # Get and test the device
            device = _get_device(self.chip, self.line)
            if device.get_line_info(line).used:
                raise ValueError('Button setup: Cannot acquire gpiochip \'{}\''\
                                  'line {}; currently used by: \'{}\''
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

        def event(self):
            ''' (wait indefinately for and) return the first event in the queue '''
            self.request.wait_edge_events(timeout=None)
            event = self.request.read_edge_events(max_events=1)[0]
            if event.line_offset == self.line:
                if event.event_type == RISING_EDGE:
                    return 'rising'
                elif event.event_type == FALLING_EDGE:
                    return 'falling'

    def __init__(self, buttons, gpio):
        ''' Creates button objects for all the specified pins
            and spawns threads to monitor them and flip the pin
            when the button is pressed '''
        self.gpio = gpio
        self.watched = {}
        self._threads = {}
        for button in buttons:
            if button not in gpio.pins.keys():
                print('Cannot configure button for undefined pin \'{}\'.'
                      .format(button))
                continue
            self.watched[button] = self._button(chip=buttons[button][0],
                                                line=buttons[button][1],
                                                consumer=gpio._consumer,
                                                debounce=buttons[button][3])
            self._threads[button] = Thread(target=self._serve_input,
                                           args=(button, buttons[button][2]))
            self._threads[button].daemon = True
            self._threads[button].start()
            print('Pin \'{}\' button configured on \'{}\':{} ({})'
                  .format(button, buttons[button][0],
                          buttons[button][1], buttons[button][2]))
            logging.info('Pin \'{}\' button configured on \'{}\':{} ({})'
                         .format(button, buttons[button][0],
                                 buttons[button][1], buttons[button][2]))

    def _flip(self, pin):
        ''' A simple function to invert the output '''
        current = self.gpio.pins[pin].get()
        if current == 0:
            self.gpio.setPin(pin, 1)
        elif current == 1:
            self.gpio.setPin(pin, 0)

    def _serve_input(self, pin, edge):
        '''service loop serving the input pin events (run in a thread)'''
        while True:
            event = self.watched[pin].event()
            if event == edge:
                self._flip(pin)
                print('Button toggle for pin \'{}\''.format(pin), flush=True)
                logging.info('Button toggle for pin \'{}\''.format(pin))

if __name__ == "__main__":
    from sys import exit
    print('ButtonWatcher class for SBCEye, see inline docs')
    exit()

