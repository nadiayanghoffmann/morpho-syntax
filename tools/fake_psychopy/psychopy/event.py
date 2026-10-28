"""Fake psychopy.event: every key wait is answered at once with the first allowed key that isn't Escape."""


def waitKeys(maxWait=float('inf'), keyList=None, timeStamped=False, **kwargs):
    keys = [k for k in (keyList or ['space']) if k != 'escape']
    return [keys[0] if keys else 'space']
