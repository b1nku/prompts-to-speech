"""prompts-to-speech controller firmware (Raspberry Pi Pico, MicroPython)

Reads 5 push-buttons and reports each press to the host over USB serial as a single
newline-terminated line "B<id>", e.g. "B3\\n". The host ignores anything that does not
match that pattern, so MicroPython's boot banner and any stray output are harmless.

Button to ID mapping (GP2..GP6 -> 1..5):
    GP2 -> B1
    GP3 -> B2
    GP4 -> B3
    GP5 -> B4
    GP6 -> B5

Wiring: connect each button between its GPIO pin and GND. The internal pull-ups are
enabled, so the pin reads 1 (high) when released and 0 (low) when pressed. No external
resistors are needed.

Install: flash MicroPython to the Pico, then copy this file to the board as main.py
(for example with Thonny or `mpremote cp main.py :main.py`). It runs automatically on
power-up.
"""

from machine import Pin
import utime

# GP2..GP6 in order, so index i maps to button ID i + 1.
BUTTON_PINS = (2, 3, 4, 5, 6)

# How long a reading must hold steady before it counts, to reject contact bounce.
DEBOUNCE_MS = 20

# With pull-ups: 1 = released, 0 = pressed.
RELEASED = 1
PRESSED = 0

buttons = [Pin(gp, Pin.IN, Pin.PULL_UP) for gp in BUTTON_PINS]

# Per-button debounce state.
stable = [RELEASED] * len(buttons)        # last debounced (accepted) value
last_reading = [RELEASED] * len(buttons)  # last raw value seen
last_change = [utime.ticks_ms()] * len(buttons)

# Optional: flash the onboard LED on each press for visual confirmation. Works on
# both the Pico and Pico W in recent MicroPython builds; ignored if unavailable.
try:
    led = Pin("LED", Pin.OUT)
except (TypeError, ValueError):
    led = None


def blink():
    if led is not None:
        led.on()
        utime.sleep_ms(15)
        led.off()


while True:
    now = utime.ticks_ms()
    for i, btn in enumerate(buttons):
        reading = btn.value()

        # Reset the debounce timer whenever the raw reading changes.
        if reading != last_reading[i]:
            last_reading[i] = reading
            last_change[i] = now
        # Accept the reading once it has been stable long enough.
        elif utime.ticks_diff(now, last_change[i]) >= DEBOUNCE_MS:
            if reading != stable[i]:
                stable[i] = reading
                # Fire only on the press edge, not the release.
                if reading == PRESSED:
                    print("B{}".format(i + 1))
                    blink()

    utime.sleep_ms(5)
