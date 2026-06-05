"""prompts-to-speech controller firmware (Raspberry Pi Pico, MicroPython)

Reads 5 push-buttons and reports each press to the host over USB serial as a single
newline-terminated line "B<id>", e.g. "B3\\n". The host ignores anything that does not
match that pattern, so MicroPython's boot banner and any stray output are harmless.

An external LED on GP15 is driven by the host, not by the press: the host blinks it
during its "thinking" pause by sending "L1\\n"/"L0\\n" (LED on/off), which this firmware
reads without blocking the button scan.

The onboard BOOTSEL button is also read and reported as "B0", which the host turns
into a random answer drawn from every button's prompts. No wiring is needed for it.

Button to ID mapping (GP2..GP6 -> 1..5, onboard BOOTSEL -> 0):
    GP2 -> B1
    GP3 -> B2
    GP4 -> B3
    GP5 -> B4
    GP6 -> B5
    BOOTSEL -> B0

Wiring: connect each button between its GPIO pin and GND. The internal pull-ups are
enabled, so the pin reads 1 (high) when released and 0 (low) when pressed. No external
resistors are needed.

LED: GP15 -> resistor (~220-330 ohm) -> LED anode, LED cathode -> GND. The pin is
driven high to light it ("L1"), low to turn it off ("L0").

Install: flash MicroPython to the Pico, then copy this file to the board as main.py
(for example with Thonny or `mpremote cp main.py :main.py`). It runs automatically on
power-up.
"""

from machine import Pin
import rp2
import sys
import uselect
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

# Onboard BOOTSEL button, read via rp2.bootsel_button() -> reports as "B0". Unlike the
# wired buttons it reads 1 when pressed and 0 when released, so it gets its own state.
BOOTSEL_PRESSED = 1
BOOTSEL_RELEASED = 0
bootsel_stable = BOOTSEL_RELEASED
bootsel_last = BOOTSEL_RELEASED
bootsel_change = utime.ticks_ms()

# External "thinking" LED on GP15, driven by the host over serial (see poll_host).
# Wired active-high to GND, so led.on() lights it.
LED_PIN = 15
led = Pin(LED_PIN, Pin.OUT)
led.off()

# Non-blocking reader for host -> controller LED commands on stdin (USB serial).
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)
rx_buf = ""


def poll_host():
    """Apply any pending LED commands from the host without blocking the scan.

    Reads one character at a time only while data is waiting, accumulating a line.
    "L1" turns the LED on, "L0" off; anything else is ignored.
    """
    global rx_buf
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            cmd, rx_buf = rx_buf, ""
            if cmd == "L1":
                led.on()
            elif cmd == "L0":
                led.off()
        else:
            rx_buf += ch
            if len(rx_buf) > 8:  # guard against an unterminated flood
                rx_buf = ""


while True:
    poll_host()
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
                # Fire only on the press edge, not the release. The LED is left to
                # the host, which blinks it during its thinking pause.
                if reading == PRESSED:
                    print("B{}".format(i + 1))

    # Same debounce, separately, for the onboard BOOTSEL button -> "B0".
    bootsel_reading = rp2.bootsel_button()
    if bootsel_reading != bootsel_last:
        bootsel_last = bootsel_reading
        bootsel_change = now
    elif utime.ticks_diff(now, bootsel_change) >= DEBOUNCE_MS:
        if bootsel_reading != bootsel_stable:
            bootsel_stable = bootsel_reading
            if bootsel_reading == BOOTSEL_PRESSED:
                print("B0")

    utime.sleep_ms(5)
