/*
 * prompts-to-speech controller firmware (Arduino Nano)
 *
 * Reads 5 push-buttons and reports each press to the host over USB serial as a
 * single line "B<id>", e.g. "B3". The host strips trailing whitespace and ignores
 * anything that does not match, so the CR/LF that println() adds is harmless.
 *
 * Button to ID mapping (D2..D6 -> 1..5):
 *     D2 -> B1
 *     D3 -> B2
 *     D4 -> B3
 *     D5 -> B4
 *     D6 -> B5
 *
 * Wiring: connect each button between its digital pin and GND. INPUT_PULLUP is
 * enabled, so the pin reads HIGH when released and LOW when pressed. No external
 * resistors are needed.
 *
 * The baud rate must match the host (115200). Unlike the Pico's native USB, the
 * Nano's USB-to-serial chip uses this rate for real, so it has to agree on both ends.
 */

const uint8_t BUTTON_PINS[] = {2, 3, 4, 5, 6};
const uint8_t NUM_BUTTONS = sizeof(BUTTON_PINS) / sizeof(BUTTON_PINS[0]);

// How long a reading must hold steady before it counts, to reject contact bounce.
const unsigned long DEBOUNCE_MS = 20;

// With pull-ups: HIGH = released, LOW = pressed.
int stableState[NUM_BUTTONS];   // last debounced (accepted) value
int lastReading[NUM_BUTTONS];   // last raw value seen
unsigned long lastChange[NUM_BUTTONS];

void blink() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(15);
  digitalWrite(LED_BUILTIN, LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    pinMode(BUTTON_PINS[i], INPUT_PULLUP);
    stableState[i] = HIGH;
    lastReading[i] = HIGH;
    lastChange[i] = 0;
  }
}

void loop() {
  unsigned long now = millis();
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    int reading = digitalRead(BUTTON_PINS[i]);

    // Reset the debounce timer whenever the raw reading changes.
    if (reading != lastReading[i]) {
      lastReading[i] = reading;
      lastChange[i] = now;
    }
    // Accept the reading once it has been stable long enough.
    else if (now - lastChange[i] >= DEBOUNCE_MS) {
      if (reading != stableState[i]) {
        stableState[i] = reading;
        // Fire only on the press edge, not the release.
        if (reading == LOW) {
          Serial.print('B');
          Serial.println(i + 1);
          blink();
        }
      }
    }
  }
}
