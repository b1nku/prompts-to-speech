/*
 * prompts-to-speech controller firmware (Arduino Nano)
 *
 * Reads 5 push-buttons and reports each press to the host over USB serial as a
 * single line "B<id>", e.g. "B3". The host strips trailing whitespace and ignores
 * anything that does not match, so the CR/LF that println() adds is harmless.
 *
 * An external LED on D9 is driven by the host, not by the press: the host blinks it
 * during its "thinking" pause by sending "L1"/"L0" (LED on/off), which pollHost()
 * reads without blocking the button scan.
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
 * resistors are needed for the buttons.
 *
 * LED: D9 -> resistor (~220-330 ohm) -> LED anode, LED cathode -> GND. The pin is
 * driven HIGH to light it ("L1"), LOW to turn it off ("L0").
 *
 * The baud rate must match the host (115200). Unlike the Pico's native USB, the
 * Nano's USB-to-serial chip uses this rate for real, so it has to agree on both ends.
 */

const uint8_t BUTTON_PINS[] = {2, 3, 4, 5, 6};
const uint8_t NUM_BUTTONS = sizeof(BUTTON_PINS) / sizeof(BUTTON_PINS[0]);

// External "thinking" LED, wired active-high to GND, so HIGH lights it.
const uint8_t LED_PIN = 9;

// How long a reading must hold steady before it counts, to reject contact bounce.
const unsigned long DEBOUNCE_MS = 20;

// With pull-ups: HIGH = released, LOW = pressed.
int stableState[NUM_BUTTONS];   // last debounced (accepted) value
int lastReading[NUM_BUTTONS];   // last raw value seen
unsigned long lastChange[NUM_BUTTONS];

// Apply any pending LED commands from the host without blocking the scan. Reads
// whatever bytes are waiting, accumulating a line; "L1" turns the LED on, "L0" off.
void pollHost() {
  static char buf[8];
  static uint8_t len = 0;
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      buf[len] = '\0';
      if (strcmp(buf, "L1") == 0) digitalWrite(LED_PIN, HIGH);
      else if (strcmp(buf, "L0") == 0) digitalWrite(LED_PIN, LOW);
      len = 0;
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    } else {
      len = 0;  // overflow on an unterminated flood; resync on the next newline
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  for (uint8_t i = 0; i < NUM_BUTTONS; i++) {
    pinMode(BUTTON_PINS[i], INPUT_PULLUP);
    stableState[i] = HIGH;
    lastReading[i] = HIGH;
    lastChange[i] = 0;
  }
}

void loop() {
  pollHost();
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
        // Fire only on the press edge, not the release. The LED is left to the
        // host, which blinks it during its thinking pause.
        if (reading == LOW) {
          Serial.print('B');
          Serial.println(i + 1);
        }
      }
    }
  }
}
