"""prompts-to-speech (runtime)

Listens for button presses from a microcontroller over USB serial, picks a random
answer for the pressed button, and plays the matching pre-rendered audio file
through the Mac mini's speaker.

This runs fully offline. Audio is generated ahead of time by generate_audio.py, so
no network or API access is needed while it runs.

The serial port is auto-detected by USB vendor ID, so you normally do not need to
configure it. Set SERIAL_PORT in .env only to force a specific device.

Serial protocol: one newline-terminated ASCII line per press, formatted "B<id>",
e.g. "B3\\n" for button 3. Lines that don't match are ignored, so boot banners and
debug output from the controller are skipped safely.

The host also talks back: after a press it pauses for a short "thinking" beat before
speaking the answer, and during that beat it blinks the controller's onboard LED by
sending "L1\\n"/"L0\\n" (LED on/off). The --debug and --web test modes have no
controller, so they keep the pause but skip the LED.

Run with --debug to open an on-screen panel of buttons, or --web to serve a button
panel on the local network (press it from a phone). Both are for testing the pipeline
without a controller attached.
"""

import os
import random
import re
import subprocess
import sys
import time

import serial
from serial.tools import list_ports
from dotenv import load_dotenv

import launchagent
from config import AUDIO_DIR, CONFIG_PATH, all_lines, audio_filename, load_buttons

# Matches a button-press line like "B3". Anything else on the wire is ignored.
BUTTON_LINE = re.compile(rb"^B([1-5])\s*$")

# Native USB vendor IDs for the boards themselves. This is the most reliable signal:
# the board identifies itself, not a generic chip shared with other peripherals.
BOARD_VIDS = {
    0x2E8A: "Raspberry Pi (Pico)",
    0x2341: "Arduino",
    0x2A03: "Arduino (arduino.org)",
}

# Generic USB-to-serial chips used by Nano clones. Less reliable, since unrelated
# adapters can use the same chips, so these are only tried if no board-native
# device is found.
UART_VIDS = {
    0x1A86: "CH340",
    0x0403: "FTDI",
    0x10C4: "CP210x",
}


def find_serial_port(preferred: str | None = None) -> str | None:
    """Auto-detect the controller's serial device by USB vendor ID.

    If `preferred` is set and present, it wins. Otherwise prefer a board-native
    device (Pico/Arduino), then fall back to a generic USB-serial adapter.
    """
    ports = list(list_ports.comports())

    if preferred:
        if any(p.device == preferred for p in ports):
            return preferred
        print(f"SERIAL_PORT={preferred} not present; falling back to auto-detect.", file=sys.stderr)

    for vids in (BOARD_VIDS, UART_VIDS):
        matches = [p for p in ports if p.vid in vids]
        if matches:
            if len(matches) > 1:
                names = ", ".join(p.device for p in matches)
                print(f"Multiple candidate ports found ({names}); using {matches[0].device}. "
                      f"Set SERIAL_PORT in .env to pick a specific one.", file=sys.stderr)
            return matches[0].device

    return None


def print_ports() -> None:
    """List all serial ports and whether each looks like a known controller."""
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    for p in ports:
        vid = p.vid
        if vid in BOARD_VIDS:
            tag = f"<- {BOARD_VIDS[vid]}"
        elif vid in UART_VIDS:
            tag = f"<- {UART_VIDS[vid]} (generic adapter)"
        else:
            tag = ""
        vidpid = f"{vid:04x}:{p.pid:04x}" if vid and p.pid else "?"
        print(f"  {p.device}  [{vidpid}]  {p.description}  {tag}".rstrip())


def pick_answer(prompts: list[list[str]]) -> str:
    """Pick a random prompt, then a random answer within it (two-stage)."""
    return random.choice(random.choice(prompts))


# How long to "think" between a press and the spoken answer, and how fast the LED
# blinks during that pause. The blink interval is the LED's on (or off) time, so one
# full on+off cycle takes twice this.
THINKING_DELAY = 1.75   # seconds
BLINK_INTERVAL = 0.12   # seconds


def set_led(ser: "serial.Serial | None", on: bool) -> None:
    """Turn the controller's onboard LED on or off over serial. No-op without one."""
    if ser is None:
        return
    try:
        ser.write(b"L1\n" if on else b"L0\n")
    except serial.SerialException:
        pass  # controller went away mid-blink; playback still proceeds


def think(ser: "serial.Serial | None", duration: float = THINKING_DELAY) -> None:
    """Pause for the "thinking" beat, blinking the controller LED if one is connected.

    Without a controller (debug/web modes) this just sleeps, so the pacing matches.
    """
    deadline = time.monotonic() + duration
    on = True
    while time.monotonic() < deadline:
        set_led(ser, on)
        on = not on
        time.sleep(BLINK_INTERVAL)
    set_led(ser, False)  # leave the LED off afterwards


# Absolute path so it resolves under launchd's minimal PATH.
AFPLAY = "/usr/bin/afplay"


def play(path: str) -> None:
    """Play an audio file through the Mac mini's speaker via macOS afplay."""
    afplay = AFPLAY if os.path.exists(AFPLAY) else "afplay"
    subprocess.run([afplay, path], check=True)


def check_audio(buttons: dict[int, list[list[str]]]) -> bool:
    """Warn about any line missing its pre-rendered audio file. Returns True if all present."""
    missing = [
        text for text in all_lines(buttons)
        if not os.path.exists(os.path.join(AUDIO_DIR, audio_filename(text)))
    ]
    if missing:
        print(f"WARNING: {len(missing)} line(s) have no audio file. Run generate_audio.py:", file=sys.stderr)
        for text in missing:
            print(f"  missing: {text!r}", file=sys.stderr)
        return False
    return True


def handle_press(button_id: int, buttons: dict[int, list[list[str]]],
                 ser: "serial.Serial | None" = None) -> None:
    """Pick a random answer for a button and play it. Shared by serial and debug GUI.

    `ser`, when given, is the open controller connection used to blink its LED during
    the thinking pause; the debug/web modes pass None and just get the pause.
    """
    prompts = buttons.get(button_id)
    if not prompts:
        print(f"Button {button_id} has no prompts configured.")
        return
    text = pick_answer(prompts)
    path = os.path.join(AUDIO_DIR, audio_filename(text))
    if not os.path.exists(path):
        print(f"Button {button_id} -> {text!r} (NO AUDIO, skipping)", file=sys.stderr)
        return
    print(f"Button {button_id} -> {text!r}")
    think(ser)  # blink the LED and pause, as if pondering, before answering
    play(path)


def run(no_install: bool = False) -> None:
    load_dotenv()

    # On first ever run, install the launchd agent and hand off to it. launchd will
    # start its own copy (which passes --no-install), so we exit here to avoid two
    # instances fighting over the serial port.
    if not no_install and not launchagent.agent_installed():
        print("First run: installing launchd agent so this starts on boot.")
        launchagent.install_agent(__file__)
        print("Handing off to launchd. This foreground instance will now exit.")
        return

    preferred = os.environ.get("SERIAL_PORT") or None
    baud = int(os.environ.get("SERIAL_BAUD", "115200"))

    buttons = load_buttons(CONFIG_PATH)
    check_audio(buttons)

    print(f"Loaded {len(buttons)} button(s) from {CONFIG_PATH}")
    print("Auto-detecting controller. Press Ctrl-C to stop.")

    # Outer loop re-detects and reconnects if the controller is unplugged or reset.
    # Re-detecting each time handles the device path changing between replugs.
    while True:
        try:
            port = find_serial_port(preferred)
            if port is None:
                print("No controller detected. Waiting...", file=sys.stderr)
                time.sleep(2)
                continue

            with serial.Serial(port, baud, timeout=1) as ser:
                print(f"Connected on {port} @ {baud} baud.")
                for raw in ser:
                    match = BUTTON_LINE.match(raw.strip())
                    if not match:
                        continue
                    handle_press(int(match.group(1)), buttons, ser)
        except serial.SerialException as e:
            print(f"Serial error: {e}. Rescanning in 2s...", file=sys.stderr)
            time.sleep(2)
        except KeyboardInterrupt:
            print("\nStopping.")
            return


def run_debug_gui() -> None:
    """Open a window with one button per configured button, for testing without a
    controller. Clicking a button runs the same answer-selection and playback as a
    real press. Touches neither serial nor launchd.
    """
    import threading
    import tkinter as tk

    load_dotenv()
    buttons = load_buttons(CONFIG_PATH)
    check_audio(buttons)
    print(f"Debug GUI: {len(buttons)} button(s) from {CONFIG_PATH}. No controller needed.")

    def on_click(button_id: int) -> None:
        # Play in a background thread so afplay does not freeze the window.
        threading.Thread(target=handle_press, args=(button_id, buttons), daemon=True).start()

    root = tk.Tk()
    root.title("prompts-to-speech (debug)")
    tk.Label(root, text="Debug mode: no controller. Click a button to simulate a press.").pack(
        padx=16, pady=(16, 8))
    frame = tk.Frame(root)
    frame.pack(padx=16, pady=(0, 16))
    for col, button_id in enumerate(sorted(buttons)):
        tk.Button(frame, text=f"Button {button_id}", width=12, height=3,
                  command=lambda b=button_id: on_click(b)).grid(row=0, column=col, padx=4)
    root.mainloop()


# Mobile-friendly control page. {buttons} is replaced with the button markup. Other
# braces are CSS/JS, so this is built with .replace(), not str.format().
_WEB_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>prompts-to-speech</title>
<style>
  :root { color-scheme: dark light; }
  body { margin:0; font-family:-apple-system,system-ui,sans-serif; background:#111; color:#eee;
         display:flex; flex-direction:column; min-height:100vh; }
  header { padding:16px; text-align:center; opacity:.7; }
  .grid { flex:1; display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:12px; }
  button { font-size:1.5rem; border:none; border-radius:16px; background:#2563eb; color:#fff;
           padding:32px 0; touch-action:manipulation; transition:transform .05s, background .15s; }
  button:active { transform:scale(.96); }
  button.flash { background:#16a34a; }
</style>
</head>
<body>
<header>prompts-to-speech &mdash; tap a button</header>
<div class="grid">
{buttons}
</div>
<script>
async function press(id, el){
  el.classList.add('flash');
  setTimeout(function(){ el.classList.remove('flash'); }, 200);
  try { await fetch('/press/' + id, {method:'POST'}); } catch(e){}
}
</script>
</body>
</html>
"""


def get_lan_ip() -> str:
    """Best-effort local network IP, so we can print a URL the phone can reach."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No packets are actually sent; this just selects the outbound interface.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def run_web_server(port: int = 8000) -> None:
    """Serve a button panel on the local network so a phone can trigger presses.

    Reuses handle_press, so behaviour matches a real controller. Touches neither
    serial nor launchd.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    load_dotenv()
    buttons = load_buttons(CONFIG_PATH)
    check_audio(buttons)

    markup = "\n".join(
        f'  <button onclick="press({bid}, this)">Button {bid}</button>'
        for bid in sorted(buttons)
    )
    page = _WEB_PAGE.replace("{buttons}", markup).encode("utf-8")
    press_path = re.compile(r"^/press/([1-9]\d*)$")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # quiet; handle_press already logs each press

        def _send(self, code, body, content_type):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, page, "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            match = press_path.match(self.path)
            if match and int(match.group(1)) in buttons:
                threading.Thread(target=handle_press, args=(int(match.group(1)), buttons),
                                 daemon=True).start()
                self._send(200, b'{"ok":true}', "application/json")
            else:
                self._send(404, b'{"ok":false}', "application/json")

    ip = get_lan_ip()
    print(f"Loaded {len(buttons)} button(s) from {CONFIG_PATH}")
    print("Web control panel running. Open on a phone on the same network:")
    print(f"  http://{ip}:{port}")
    print(f"  http://localhost:{port}  (this machine)")
    print("Press Ctrl-C to stop.")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    if "--list-ports" in sys.argv:
        print_ports()
    elif "--install" in sys.argv:
        launchagent.install_agent(__file__)
    elif "--uninstall" in sys.argv:
        launchagent.uninstall_agent()
    elif "--debug" in sys.argv:
        # On-screen buttons for testing without a controller.
        run_debug_gui()
    elif "--web" in sys.argv:
        # Button panel served on the LAN; press from a phone. Optional: --port N.
        port = 8000
        if "--port" in sys.argv:
            try:
                port = int(sys.argv[sys.argv.index("--port") + 1])
            except (IndexError, ValueError):
                print("--port needs a number; using 8000.", file=sys.stderr)
        run_web_server(port)
    else:
        # --no-install runs in the foreground without touching launchd, which is
        # what the launchd-managed instance uses and what you want for debugging.
        run(no_install="--no-install" in sys.argv)
