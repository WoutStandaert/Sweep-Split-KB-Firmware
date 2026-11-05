# Sweep-Split-KB-Firmware

Firmware and a configurator for a **Ferris Sweep** split keyboard with **Adafruit KB2040** controllers. It runs [KMK](https://github.com/KMKfw/kmk_firmware) on CircuitPython instead of QMK:

- **Nothing to compile.** The keymap is a JSON file on the keyboard's USB drive. When you save it, the keyboard reloads.
- **A reliable link between the halves.** The TRRS cable has one data wire, between both halves' RX pins (GP1). The RP2040's PIO hardware drives it, which avoids the serial driver and pin setup that often made the link flaky under QMK.
- **A visual configurator** that runs in your browser on your PC. It's one HTML file: no install, no server and no internet needed.

Tested on hardware: both halves run CircuitPython 10.3.1 with KMK, and key presses from the right half reach the left half over the TRRS cable.

```
firmware/code.py         KMK firmware: pin map, split link, keymap.json loader
firmware/keymap.json     default 3-layer keymap (Base, Symbols, Nav)
configurator/index.html  browser configurator (Chrome or Edge)
install.ps1              installs KMK + firmware onto one half (Windows)
```

## Setup (once per half)

1. **CircuitPython.** Download the latest stable `.uf2` for the KB2040 from https://circuitpython.org/board/adafruit_kb2040/. Unplug the TRRS cable, hold **BOOT** while plugging the half into USB, then copy the `.uf2` onto the `RPI-RP2` drive that appears. After a few seconds a `CIRCUITPY` drive appears.
2. **Firmware.** From this folder, run (use the drive letter it got):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Drive E -Side L
   ```
   This downloads KMK, copies `kmk/`, `code.py` and `keymap.json` onto the half, and renames its drive to `SWEEPL`. It keeps an existing `keymap.json` unless you add `-OverwriteKeymap`. Repeat for the right half with `-Side R`, which names it `SWEEPR`.
3. **Connect.** With both halves unplugged, connect the TRRS cable, then plug **one** half into USB. Never plug or unplug the TRRS cable while the keyboard is powered: it can short pins and damage the link.

On macOS or Linux, do step 2 by hand: copy the `kmk/` folder from the KMK repository plus `firmware/code.py` and `firmware/keymap.json` to the drive root, then rename the drive to `SWEEPL` or `SWEEPR`.

The half on USB is the primary, and its `keymap.json` is the one in use. Plug in the same half every time (the left half, normally), or keep both halves' keymaps the same.

## Configurator

Open `configurator/index.html` in Chrome or Edge, click **Open keyboard drive…**, pick the `SWEEPL` drive, make your changes, then click **Save to keyboard**. Next time, one click on **Reconnect** is enough. In other browsers, or if the browser won't open the drive, use **More ▸ Download keymap.json** and copy the file onto the drive yourself.

- Click a key to edit it. Pick what it types from the palette, add modifiers ("with mods"), and choose what it does when held: a modifier (home-row mods) or a layer.
- **Press a key…** assigns whatever you type next, including shortcuts like Ctrl+C.
- Layers: add, rename, duplicate, reorder and delete them. Keys that point at a layer are renumbered when layers move.
- Combos: click keys on the board to choose them, and set what they output.
- Timing: the hold threshold, the combo window and debounce.
- Keyboard shortcuts: arrow keys move the selection, `Del` makes a key transparent, `Ctrl+Z`/`Ctrl+Y` undo and redo, `Ctrl+S` saves.
- Invalid keys are outlined in red, so mistakes show up before you save.

## Status LED

| LED | Meaning |
|---|---|
| short green flash | keymap loaded |
| yellow | drive label doesn't end in L or R |
| magenta | some keys in keymap.json are invalid (the serial console says which) |
| red | keymap.json missing or not valid JSON, so a plain QWERTY fallback is in use |

## keymap.json

Each layer has 34 keys, listed in visual order:

```
 0  1  2  3  4      5  6  7  8  9
10 11 12 13 14     15 16 17 18 19
20 21 22 23 24     25 26 27 28 29
         30 31     32 33
```

Key names are KMK names without the `KC.` prefix:

| Write | Means |
|---|---|
| `A`, `N1`, `SPC`, `BSPC`, `LEFT`, `F5` | plain keys (digits are `N0`–`N9`) |
| `LCTL(C)`, `LCTL(LSFT(T))` | key with modifiers |
| `HT(A, LGUI)` | tap for A, hold for GUI |
| `HT(F, LSFT, tap_time=180)` | same, with its own hold threshold |
| `LT(1, SPC)` | tap for Space, hold for layer 1 |
| `MO(2)`, `TG(1)`, `TO(0)`, `DF(0)` | layer keys (hold, toggle, go to, set default) |
| `MB_LMB`, `MS_UP`, `MW_DOWN` | mouse buttons, movement, scroll |
| `VOLU`, `MUTE`, `MPLY` | media keys |
| `TRNS` / `NO` | fall through to the layer below / do nothing |
| `BOOTLOADER`, `RELOAD` | reboot into UF2 mode / reload the firmware |

Combos are matched by key position, so they work on every layer:

```json
"combos": [ { "keys": [16, 17], "output": "ESC" } ]
```

Settings: `tap_time` (ms before a hold-tap counts as held), `combo_timeout` (ms within which a combo's keys must all be pressed), `debounce_ms`.

## Hardware notes

The Sweep PCB is reversible, so both halves use the same pin list and the firmware mirrors the right half in software. The Pro Micro → KB2040 pin map matches QMK's `ferris/sweep` with the `kb2040` converter:

| Row | Pro Micro pins (outer → inner) | KB2040 GPIO |
|---|---|---|
| Top | E6 F7 F6 F5 F4 | GP7 GP26 GP27 GP28 GP29 |
| Home | B1 B3 B2 B6 D3 | GP18 GP20 GP19 GP10 GP0 |
| Bottom | D1 D0 D4 C6 D7 | GP2 GP3 GP4 GP5 GP6 |
| Thumbs | B4 B5 | GP8 GP9 |
| TRRS data | D2 | GP1 (RX) |

Data over the link only goes one way: the half without USB sends its key events to the USB half at 9600 baud.

## Troubleshooting

To read the serial console, use the KB2040's USB serial port at 115200 baud. Mu, Thonny, PuTTY or `python -m serial.tools.miniterm COMx 115200` all work. On startup the firmware prints a line like `Ferris Sweep: SWEEPL | 3 layers | 2 combos | 0 errors`, followed by KMK's debug log, which lists every key press (`coordkeys_pressed=…`). Left-half keys are numbered 0–16 and right-half keys 17–33.

If the half without USB does nothing:

- Check that the drive labels end in L and R (`SWEEPL`, `SWEEPR`).
- Make sure both halves have the same `code.py` and `kmk/`.
- Try another TRRS cable (cables are a common culprit), and check the solder joints on the jacks.
- Plug the other half into USB to check that its own switches work.

## Credits

- [KMK firmware](https://github.com/KMKfw/kmk_firmware) (GPL-3.0). It isn't stored in this repository: `install.ps1` downloads it.
- The Ferris Sweep by David Philip Barr ([davidphilipbarr/Sweep](https://github.com/davidphilipbarr/Sweep)). The pin map comes from QMK's `ferris/sweep` and KMK's `boards/ferris_sweep`.
