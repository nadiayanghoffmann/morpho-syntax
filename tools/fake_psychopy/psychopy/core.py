"""Fake psychopy.core: a simulated clock so a full session runs in about a second."""

import sys
import time

# Every core.wait() moves this offset forward instead of sleeping, and time.time()
# includes it, so reaction times measured with time.time() still look realistic.
_offset = [0.0]
_real_time = time.time
time.time = lambda: _real_time() + _offset[0]


def wait(secs, hogCPUperiod=0.2):
    _offset[0] += secs


def quit():
    sys.exit(0)


class Clock:
    def __init__(self):
        self._start = time.time()

    def reset(self):
        self._start = time.time()

    def getTime(self):
        return time.time() - self._start
