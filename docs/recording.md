# Recording the voice lines

Calls ElevenLabs once per line and saves the audio under `audio/`:

```bash
python generate_audio.py
```

Lines that already have an audio file are skipped, so re-running after editing `prompts.toml` only renders new or changed lines and does not waste API credits. To re-render everything (for example after changing the voice):

```bash
python generate_audio.py --force
```

## Filenames

Each line maps to a file named from a readable slug plus a short hash of the text (e.g. `hello-there-95e3ac56.mp3`).
Changing a line's wording produces a new file and leaves the old one as a harmless orphan.
The runtime derives the same name, so the two always agree on which file holds which line.

## Committed on purpose

The rendered audio in `audio/` is committed to git (it is not gitignored), so the repo is self-contained and plays offline on any machine without regenerating.
