# Hardware

- MCU with 5 push-buttons (Raspberry Pi Pico or Arduino Nano)
- Mac mini, connected to the controller over USB

The controller's only job is to report which button was pressed.
All logic and audio live on the Mac mini, so the MCU is interchangeable.

## Serial protocol

One newline-terminated ASCII line per press: `B<id>`, where `<id>` is `1` to `5`
(pressing button 3 sends `B3\n`). The host strips trailing whitespace and ignores any
line that doesn't match, so boot banners and stray output are harmless.

- Baud: `115200`, must match on both ends.
- The firmware debounces each button and fires only on press, so one push is one line.

## Firmware: Raspberry Pi Pico

File: `firmware/pico/main.py` (MicroPython).

| GPIO | Button ID | Sends |
|------|-----------|-------|
| GP2  | 1         | `B1`  |
| GP3  | 2         | `B2`  |
| GP4  | 3         | `B3`  |
| GP5  | 4         | `B4`  |
| GP6  | 5         | `B5`  |

Wire each button between its GPIO pin and GND. Internal pull-ups are enabled, so no external resistors are needed.
The onboard LED flashes on each press.

Install: flash MicroPython, then copy the file to the board as `main.py` so it runs on power-up:

```bash
mpremote cp firmware/pico/main.py :main.py
```

Thonny works too: open the file and save it to the Pico as `main.py`.

## Firmware: Arduino Nano

File: `firmware/arduino_nano/arduino_nano.ino`.

| Pin | Button ID | Sends |
|-----|-----------|-------|
| D2  | 1         | `B1`  |
| D3  | 2         | `B2`  |
| D4  | 3         | `B3`  |
| D5  | 4         | `B4`  |
| D6  | 5         | `B5`  |

Same wiring idea as the Pico: each button between its pin and GND, `INPUT_PULLUP`
enabled, onboard LED flashes on each press.

Install: open the sketch in the Arduino IDE, select the Nano board and its port, and
upload.

Notes:
- The baud rate (115200) must match the host; the Nano's USB-serial chip uses it for real.
- The Nano resets when the serial port is opened, so the host re-detects it on each
  connection. This is expected.
