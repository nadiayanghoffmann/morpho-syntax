"""Fake psychopy.gui: skips the setup dialog, filling it from DRYRUN_* environment variables."""

import os


class DlgFromDict:
    def __init__(self, dictionary, title='', order=None, **kwargs):
        overrides = {
            'Participant ID':   os.environ.get('DRYRUN_SUBJECT', 'dryrun-01'),
            'Start from block': os.environ.get('DRYRUN_START_BLOCK', '1'),
            'Auto respond?':    True,
        }
        for key, value in overrides.items():
            if key in dictionary:
                dictionary[key] = value
        self.OK = True
