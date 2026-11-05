# Ferris Sweep (Adafruit KB2040) -- KMK firmware driven by keymap.json
#
# The keymap lives in keymap.json next to this file. Edit it with the
# configurator (configurator/index.html) or by hand; CircuitPython reloads
# automatically when the file is saved.
#
# Side detection: rename the CIRCUITPY drive so its label ends in L or R
# (for example SWEEPL / SWEEPR). The half plugged into USB becomes the
# primary; the other half sends its key presses over the TRRS cable.
#
# Status LED (NeoPixel on the KB2040):
#   green flash  -> keymap loaded fine
#   yellow       -> drive label does not end in L or R (split won't work)
#   red          -> keymap.json missing or invalid; built-in fallback in use
#   magenta      -> some keys could not be parsed (see serial console)

import json

import board
import digitalio
import microcontroller
import neopixel_write
import time
from storage import getmount

from kmk.keys import KC
from kmk.kmk_keyboard import KMKKeyboard
from kmk.modules.combos import Chord, Combos
from kmk.modules.holdtap import HoldTap
from kmk.modules.layers import Layers
from kmk.modules.mouse_keys import MouseKeys
from kmk.modules.split import Split, SplitType
from kmk.scanners.keypad import KeysScanner

try:
    from kmk.extensions.media_keys import MediaKeys
except ImportError:
    MediaKeys = None

P = microcontroller.pin

# One GPIO per switch (Ferris Sweep is direct-pin). The PCB is reversible,
# so both halves use the same list; COORD below mirrors the right half.
# Pro Micro pin -> KB2040 GPIO, same as QMK's ferris/sweep + kb2040 converter.
KEY_PINS = (
    P.GPIO7, P.GPIO26, P.GPIO27, P.GPIO28, P.GPIO29,   # top row
    P.GPIO18, P.GPIO20, P.GPIO19, P.GPIO10, P.GPIO0,   # home row
    P.GPIO2, P.GPIO3, P.GPIO4, P.GPIO5, P.GPIO6,       # bottom row
    P.GPIO8, P.GPIO9,                                  # thumbs
)

# TRRS data line: Pro Micro D2 (RX) == KB2040 GP1 on both halves.
SPLIT_DATA_PIN = P.GPIO1

# keymap.json position (visual order, left-to-right, top-to-bottom)
# -> KMK key number. Right-half key numbers are offset by 17.
# fmt: off
COORD = (
     0,  1,  2,  3,  4,   21, 20, 19, 18, 17,
     5,  6,  7,  8,  9,   26, 25, 24, 23, 22,
    10, 11, 12, 13, 14,   31, 30, 29, 28, 27,
                15, 16,   33, 32,
)
# fmt: on
NUM_KEYS = len(COORD)

FALLBACK_MAP = {
    'settings': {},
    'layers': [{
        'name': 'Fallback',
        'keys': [
            'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P',
            'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'SCLN',
            'Z', 'X', 'C', 'V', 'B', 'N', 'M', 'COMM', 'DOT', 'SLSH',
            'ESC', 'SPC', 'ENT', 'BSPC',
        ],
    }],
    'combos': [],
}


def led(r, g, b):
    try:
        pin = digitalio.DigitalInOut(board.NEOPIXEL)
        pin.direction = digitalio.Direction.OUTPUT
        neopixel_write.neopixel_write(pin, bytearray((g, r, b)))
        pin.deinit()
    except Exception:
        pass


# ---------------------------------------------------------------- key parser
# Accepts KMK-style expressions without the "KC." prefix, e.g.
#   A   SPC   LCTL(C)   LT(1, SPC)   HT(A, LGUI)   MO(2)   HT(F, LSFT, tap_time=180)
# The prefix "KC." is tolerated. "_", "TRNS" and "" mean transparent.

def _split_args(s):
    args, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur)
    if depth != 0:
        raise ValueError('unbalanced parentheses')
    return args


def _parse_value(s):
    # Bare numbers are integers (layer numbers, timeouts). Use N1..N0 for digit keys.
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    if s in ('True', 'False'):
        return s == 'True'
    return parse_key(s)


def parse_key(s):
    s = str(s).strip()
    if s.startswith('KC.'):
        s = s[3:]
    if s in ('', '_', '__', '___', 'TRNS', 'TRANSPARENT'):
        return KC.TRNS
    if s in ('NO', 'XXX', 'XXXXXXX'):
        return KC.NO
    if '(' in s:
        if not s.endswith(')'):
            raise ValueError('missing closing parenthesis')
        name, inner = s.split('(', 1)
        args, kwargs = [], {}
        for a in _split_args(inner[:-1]):
            if '=' in a and '(' not in a.split('=', 1)[0]:
                k, v = a.split('=', 1)
                kwargs[k.strip()] = _parse_value(v)
            else:
                args.append(_parse_value(a))
        return _lookup(name.strip())(*args, **kwargs)
    return _lookup(s)


def _lookup(name):
    name = name.upper()
    key = KC[name]  # KMK returns KC.NO for unknown names instead of raising
    if key is KC.NO:
        raise ValueError('unknown key ' + name)
    return key


# ------------------------------------------------------------------- loading
def load_keymap():
    try:
        with open('/keymap.json') as f:
            return json.load(f), True
    except Exception as e:
        print('keymap.json could not be loaded:', e)
        return FALLBACK_MAP, False


keymap_data, keymap_ok = load_keymap()
settings = keymap_data.get('settings', {})

keyboard = KMKKeyboard()
keyboard.matrix = KeysScanner(
    KEY_PINS,
    value_when_pressed=False,
    interval=settings.get('debounce_ms', 20) / 1000,
)
keyboard.coord_mapping = list(COORD)

label = str(getmount('/').label)
label_ok = label.endswith('L') or label.endswith('R')
if not label_ok:
    print('Drive label', label, 'does not end in L or R; split side unknown.')

split = Split(
    split_type=SplitType.UART,
    split_flip=False,          # COORD already mirrors the right half
    data_pin=SPLIT_DATA_PIN,   # single wire: secondary TX -> primary RX
    use_pio=True,              # GP1 is not a hardware UART TX pin
    uart_flip=True,
)

holdtap = HoldTap()
layers = Layers()
tap_time = settings.get('tap_time', 220)
holdtap.tap_time = tap_time
layers.tap_time = tap_time

combos = Combos()
combo_timeout = settings.get('combo_timeout', 50)

keyboard.modules = [layers, holdtap, split, combos, MouseKeys()]
if MediaKeys:
    keyboard.extensions.append(MediaKeys())

# Build layers
bad_keys = 0
layers_out = []
for li, layer in enumerate(keymap_data.get('layers', [])):
    keys = list(layer.get('keys', []))
    keys += ['NO'] * (NUM_KEYS - len(keys))
    row = []
    for pos, expr in enumerate(keys[:NUM_KEYS]):
        try:
            row.append(parse_key(expr))
        except Exception as e:
            bad_keys += 1
            print('layer', li, 'key', pos, repr(expr), '->', e)
            row.append(KC.NO)
    layers_out.append(row)
if not layers_out:
    layers_out = [[KC.NO] * NUM_KEYS]
keyboard.keymap = layers_out

# Combos are matched by physical position, so they work on every layer.
for c in keymap_data.get('combos', []):
    try:
        positions = tuple(COORD[int(p)] for p in c['keys'])
        combos.combos.append(Chord(
            positions,
            parse_key(c['output']),
            match_coord=True,
            timeout=int(c.get('timeout', combo_timeout)),
        ))
    except Exception as e:
        bad_keys += 1
        print('combo', c, '->', e)

if not keymap_ok:
    led(40, 0, 0)
elif bad_keys:
    led(30, 0, 30)
elif not label_ok:
    led(30, 25, 0)
else:
    led(0, 30, 0)
    time.sleep(0.15)
    led(0, 0, 0)

print('Ferris Sweep:', label, '|', len(layers_out), 'layers |',
      len(combos.combos), 'combos |', bad_keys, 'errors')

if __name__ == '__main__':
    keyboard.go()
