"""Fake psychopy.visual: nothing is drawn, but callOnFlip callbacks (e.g. sendTrigger) still run on flip()."""

import time


class Window:
    def __init__(self, *args, **kwargs):
        self.monitorFramePeriod = 1 / 60
        self.mouseVisible = True
        self.size = (1280, 800)
        self._on_flip = []
        self.triggers_sent = 0

    def callOnFlip(self, function, *args, **kwargs):
        self._on_flip.append((function, args, kwargs))

    def flip(self, clearBuffer=True):
        for function, args, kwargs in self._on_flip:
            if getattr(function, '__name__', '') == 'sendTrigger':
                self.triggers_sent += 1
            function(*args, **kwargs)
        self._on_flip = []
        return time.time()

    def close(self):
        print(f"[fake psychopy] window closed, {self.triggers_sent} triggers sent")


class _Stim:
    def __init__(self, win=None, text='', *args, **kwargs):
        self.text = text

    def setText(self, text):
        self.text = text

    def draw(self):
        pass


TextStim = _Stim
Rect = _Stim
ImageStim = _Stim
