"""Pre-render every line in prompts.toml to an audio file in audio/.

Run this once, ahead of time, while you have a reliable network connection. The
runtime (main.py) then plays these files offline, so it does not depend on the
network or the ElevenLabs API during the event.

Lines that already have an audio file are skipped, so re-running only synthesises
new or changed lines and does not waste API credits. Pass --force to re-render
everything.

    python generate_audio.py
    python generate_audio.py --force
"""

import os
import sys

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from config import AUDIO_DIR, CONFIG_PATH, all_lines, audio_filename, load_buttons

MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"


def main() -> None:
    load_dotenv()
    force = "--force" in sys.argv

    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    client = ElevenLabs(api_key=api_key)

    os.makedirs(AUDIO_DIR, exist_ok=True)
    buttons = load_buttons(CONFIG_PATH)
    lines = all_lines(buttons)
    print(f"{len(lines)} unique line(s) in {CONFIG_PATH}.")

    made = skipped = 0
    for text in lines:
        path = os.path.join(AUDIO_DIR, audio_filename(text))
        if os.path.exists(path) and not force:
            skipped += 1
            continue

        print(f"Synthesising: {text!r}")
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=MODEL_ID,
            output_format=OUTPUT_FORMAT,
        )
        with open(path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        made += 1

    print(f"Done. {made} created, {skipped} already existed. Files in {AUDIO_DIR}/")


if __name__ == "__main__":
    main()
