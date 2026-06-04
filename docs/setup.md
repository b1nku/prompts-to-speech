# Setup and configuration

## Install

```bash
git clone <repo-url>
cd prompts-to-speech
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Copy the example file and fill it in:

```bash
cp .env.example .env
```

- `ELEVENLABS_API_KEY` -> required for recording the voice lines (not at the event)
- `ELEVENLABS_VOICE_ID` -> the voice to synthesise with
- `SERIAL_PORT` -> optional; the port is auto-detected, set this only to force a device
- `SERIAL_BAUD` -> defaults to `115200`

`.env` is gitignored.

## Prompts and answers

Prompts, answers, and the button mapping live in `prompts.toml`.
Each `[[button]]` maps a physical button (`id` 1 to 5) to a set of prompts;
each `[[button.prompt]]` is a group of interchangeable answers:

```toml
[[button]]
id = 1

[[button.prompt]]
name = "greeting"
answers = [
  "Hello there.",
  "Hey, good to see you.",
]
```

Selection is two-stage:
A random prompt is chosen for the button, then a random answer within it.
So an answer alone under its prompt is more likely than one of several sharing a prompt. Group answers accordingly.

The `name` fields are for readability and logging only and are never spoken. Only the strings in `answers` are synthesised.
