"""
port_open_send.py
=================
Trigger sending module for MEG / StimTracker (Cedrus) hardware.

Trigger Channel Mapping (12 Conditions):
----------------------------------------
Channels 160 to 166 correspond to bits 0 to 6 on Cedrus StimTracker:
  • ch160 (bit 0, 0x01): Phrase trigger line (active for Phrase & Phrase-Loc)
  • ch161 (bit 1, 0x02): Spacing trigger line (active for Space / Spaced)
  • ch162 (bit 2, 0x04): Composition trigger line (active for Comp)
  • ch163 (bit 3, 0x08): Critical condition baseline marker line
  • ch164 (bit 4, 0x10): SSELocalizer marker line
  • ch165 (bit 5, 0x20): Lexicality Word marker line
  • ch166 (bit 6, 0x40): Lexicality Pseudoword marker line

12 Conditions and Trigger Combinations:
---------------------------------------
Critical Conditions (8):
  1. Comp  × Phrase   × Space   → [ch160, ch161, ch162, ch163] (mask: 0x0F = 15)
  2. Comp  × Phrase   × Nospace → [ch160, ch162, ch163]         (mask: 0x0D = 13)
  3. Comp  × Compound × Space   → [ch161, ch162, ch163]         (mask: 0x0E = 14)
  4. Comp  × Compound × Nospace → [ch162, ch163]                (mask: 0x0C = 12)
  5. List  × Phrase   × Space   → [ch160, ch161, ch163]         (mask: 0x0B = 11)
  6. List  × Phrase   × Nospace → [ch160, ch163]                (mask: 0x09 = 9)
  7. List  × Compound × Space   → [ch161, ch163]                (mask: 0x0A = 10)
  8. List  × Compound × Nospace → [ch163]                       (mask: 0x08 = 8)

Localizer Conditions (5):
  9.  SSELocalizer × Phrase-Loc       → [ch160, ch164]          (mask: 0x11 = 17)
  10. SSELocalizer × List-Loc         → [ch164]                 (mask: 0x10 = 16)
  11. Lexicality   × Word             → [ch165]                 (mask: 0x20 = 32)
  12. Lexicality   × Pseudoword       → [ch166]                 (mask: 0x40 = 64)
  13. Lexicality   × ConsonantString  → [ch165, ch166]          (mask: 0x60 = 96)
"""

import time
import os

try:
    import serial
except ImportError:
    serial = None

# Hardware channel to bitmask
CHANNEL_BITS = {
    'ch160': 0x01,  # bit 0: Phrase
    'ch161': 0x02,  # bit 1: Space (spaced)
    'ch162': 0x04,  # bit 2: Comp (composition)
    'ch163': 0x08,  # bit 3: Critical baseline
    'ch164': 0x10,  # bit 4: SSELocalizer
    'ch165': 0x20,  # bit 5: Lexicality Word
    'ch166': 0x40,  # bit 6: Lexicality Pseudoword
}

# 12 conditions mapping table
# Key: (TestControl, StrucLevel, Spacing) -> list of channels
TRIGGER_MAP_12 = {
    # 8 Critical conditions
    ('Comp', 'Phrase', 'Space'):        ['ch160', 'ch161', 'ch162', 'ch163'],
    ('Comp', 'Phrase', 'Nospace'):      ['ch160', 'ch162', 'ch163'],
    ('Comp', 'Compound', 'Space'):      ['ch161', 'ch162', 'ch163'],
    ('Comp', 'Compound', 'Nospace'):    ['ch162', 'ch163'],
    ('List', 'Phrase', 'Space'):        ['ch160', 'ch161', 'ch163'],
    ('List', 'Phrase', 'Nospace'):      ['ch160', 'ch163'],
    ('List', 'Compound', 'Space'):      ['ch161', 'ch163'],
    ('List', 'Compound', 'Nospace'):    ['ch163'],

    # 5 Localizer conditions
    ('SSELocalizer', 'Phrase-Loc', 'Localizer'):       ['ch160', 'ch164'],
    ('SSELocalizer', 'List-Loc', 'Localizer'):         ['ch164'],
    ('Lexicality', 'Word', 'Localizer'):               ['ch165'],
    ('Lexicality', 'Pseudoword', 'Localizer'):         ['ch166'],
    ('Lexicality', 'ConsonantString', 'Localizer'):    ['ch165', 'ch166'],
}

TRIGGER_MAP_13 = TRIGGER_MAP_12

# Condition display labels and IDs 1 to 13
CONDITION_INFO_12 = {
    1:  {'key': ('Comp', 'Phrase', 'Space'),        'label': 'Comp Phrase Space',     'channels': ['ch160', 'ch161', 'ch162', 'ch163']},
    2:  {'key': ('Comp', 'Phrase', 'Nospace'),      'label': 'Comp Phrase Nospace',   'channels': ['ch160', 'ch162', 'ch163']},
    3:  {'key': ('Comp', 'Compound', 'Space'),      'label': 'Comp Compound Space',   'channels': ['ch161', 'ch162', 'ch163']},
    4:  {'key': ('Comp', 'Compound', 'Nospace'),    'label': 'Comp Compound Nospace', 'channels': ['ch162', 'ch163']},
    5:  {'key': ('List', 'Phrase', 'Space'),        'label': 'List Phrase Space',     'channels': ['ch160', 'ch161', 'ch163']},
    6:  {'key': ('List', 'Phrase', 'Nospace'),      'label': 'List Phrase Nospace',   'channels': ['ch160', 'ch163']},
    7:  {'key': ('List', 'Compound', 'Space'),      'label': 'List Compound Space',   'channels': ['ch161', 'ch163']},
    8:  {'key': ('List', 'Compound', 'Nospace'),    'label': 'List Compound Nospace', 'channels': ['ch163']},
    9:  {'key': ('SSELocalizer', 'Phrase-Loc', 'Localizer'),    'label': 'SSELoc Phrase',       'channels': ['ch160', 'ch164']},
    10: {'key': ('SSELocalizer', 'List-Loc', 'Localizer'),      'label': 'SSELoc List',         'channels': ['ch164']},
    11: {'key': ('Lexicality', 'Word', 'Localizer'),            'label': 'Lex Word',            'channels': ['ch165']},
    12: {'key': ('Lexicality', 'Pseudoword', 'Localizer'),      'label': 'Lex Pseudoword',      'channels': ['ch166']},
    13: {'key': ('Lexicality', 'ConsonantString', 'Localizer'), 'label': 'Lex ConsonantString', 'channels': ['ch165', 'ch166']},
}
CONDITION_INFO_13 = CONDITION_INFO_12


def channels_to_mask(channels):
    """Convert channel name, list of channel names, or int to integer bitmask."""
    if isinstance(channels, int):
        return channels
    if isinstance(channels, str):
        channels = [channels]
    mask = 0
    for ch in channels:
        if ch in CHANNEL_BITS:
            mask |= CHANNEL_BITS[ch]
    return mask


def get_condition_channels(test_control, struc_level, spacing):
    """Look up active channels for a given condition triplet."""
    key = (str(test_control).strip(), str(struc_level).strip(), str(spacing).strip())
    if key in TRIGGER_MAP_12:
        return TRIGGER_MAP_12[key]
    # Fallback / partial matching
    if test_control == 'SSELocalizer':
        if 'Phrase' in struc_level:
            return ['ch160', 'ch164']
        return ['ch164']
    if test_control == 'Lexicality':
        if struc_level == 'Word':
            return ['ch165']
        if struc_level in ('Pseudoword', 'Nonword'):
            return ['ch166']
        if struc_level in ('ConsonantString', 'Consonant String', 'consonant string'):
            return ['ch165', 'ch166']
    # Fallback for critical conditions
    channels = ['ch163']
    if 'Phrase' in struc_level:
        channels.append('ch160')
    if spacing == 'Space':
        channels.append('ch161')
    if test_control == 'Comp':
        channels.append('ch162')
    return channels


# ── Serial Port Setup ─────────────────────────────────────────────────────────
ser = None
port_path = os.environ.get('MEG_SERIAL_PORT', '/dev/cu.usbserial-A900a2R9')

def get_serial_connection():
    """Lazily open serial connection if hardware device exists."""
    global ser
    if ser is not None:
        return ser

    if serial is None:
        return None

    if not os.path.exists(port_path):
        # Device not connected (e.g. running on laptop)
        return None

    try:
        ser = serial.Serial(port=port_path, baudrate=115200, timeout=0.1)
        print(f"[port_open_send] Connected to trigger port: {port_path}")
    except Exception as e:
        ser = None
        print(f"[port_open_send] Serial port not opened ({e}). Running in simulation/mock mode.")
    return ser

# Attempt initial connection only if device file is present
if os.path.exists(port_path):
    get_serial_connection()
else:
    print(f"[port_open_send] Device {port_path} not connected. Trigger simulation/mock mode active.")


def sendTrigger(channel, duration=0.01, zero_marker=b'mh\x00'):
    """
    Send trigger to Cedrus StimTracker via serial port.

    Parameters
    ----------
    channel : str, list of str, tuple, or int
        Either single channel ('ch160'), list of channels (['ch160', 'ch161']),
        condition tuple ('Comp', 'Phrase', 'Space'), or integer bitmask.
    duration : float
        Pulse duration in seconds (default 0.01s = 10 ms).
    zero_marker : bytes
        Command bytes to reset pulse lines to 0 (default b'mh\\x00').
    """
    if isinstance(channel, tuple):
        channels = TRIGGER_MAP_12.get(channel, ['ch163'])
        mask = channels_to_mask(channels)
    else:
        mask = channels_to_mask(channel)

    data = b'mh' + bytes([mask])

    if ser is not None and ser.is_open:
        try:
            # Send marker twice as in NYU MEG lab convention
            ser.write(data)
            ser.write(data)
            ser.flush()

            time.sleep(duration)

            ser.write(zero_marker)
            ser.write(zero_marker)
            ser.flush()
        except Exception as e:
            print(f"[port_open_send] Error writing trigger {channel}: {e}")
    else:
        # Mock mode printout for testing
        active = [ch for ch, b in CHANNEL_BITS.items() if (mask & b)]
        # Silent or debug log
        pass
