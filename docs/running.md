# Running

Works offline:
Listens for button presses on the serial port and plays the matching pre-rendered audio file:

```bash
python main.py
```

On startup it warns about any configured line missing its audio file, so record the
audio first (see [recording.md](recording.md)).

## Debug mode (no controller)

To test the pipeline without a Pico or Nano attached, open an on-screen panel with one
button per configured button:

```bash
python main.py --debug
```

Clicking a button runs the exact same answer-selection and playback as a real press.
It touches neither serial nor launchd, so it's safe to run anywhere. This is a manual
mode you opt into; the normal runtime never pops up a window on its own.

## Web control (press from a phone)

Serve a button panel on the local network and tap it from a phone on the same Wi-Fi.
No screen needed on the Mac mini:

```bash
python main.py --web            # default port 8000
python main.py --web --port 8080
```

It prints a URL like `http://192.168.1.42:8000` to open on the phone. Each tap runs the
same playback as a real press. Stdlib only, no extra dependency.

Notes:
- The first run may trigger a macOS firewall prompt to allow incoming connections; allow it.
- There is no authentication: anyone on the network can press the buttons. Fine for a
  trusted booth network, but don't expose it beyond the local LAN.
- Works without internet as long as there is a local network (a Wi-Fi router or access
  point). If the printed IP looks wrong, check the Mac's address in System Settings > Network.

## Serial auto-detection

The port is auto-detected by USB vendor ID (the Pico and Arduino boards identify
themselves). 
Detection re-runs on every reconnect, so a device path that changes between re-plugs is handled automatically.

```bash
python main.py --list-ports
```

Set `SERIAL_PORT` in `.env` only to force a specific device, for example if another serial adapter is plugged into the Mac mini.

## Running on boot (launchd)

The first time you run `python main.py`, it installs a launchd LaunchAgent
(`local.prompts-to-speech`) that starts the runtime on login and restarts it if it
exits, then hands off to launchd and exits the foreground process (so two instances
don't compete for the serial port).

From then on, launchd owns it.

Logs go to `logs/stdout.log` and `logs/stderr.log`.

### Managing the agent

```bash
python main.py --install      # (re)install and load the agent
python main.py --uninstall    # stop and remove the agent
python main.py --no-install   # run in the foreground without touching launchd
```

To debug interactively,
stop the managed agent first so it isn't holding the serial port,
then run in the foreground:

```bash
python main.py --uninstall    # or: launchctl bootout gui/$(id -u)/local.prompts-to-speech
python main.py --no-install
```
