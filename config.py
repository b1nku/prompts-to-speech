"""Shared config + audio-path logic used by both generate_audio.py and main.py.

Keeping the filename derivation in one place guarantees the generator and the
runtime always agree on which file holds which line.
"""

import hashlib
import re
import tomllib

CONFIG_PATH = "prompts.toml"
AUDIO_DIR = "audio"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def load_buttons(path: str = CONFIG_PATH) -> dict[int, list[list[str]]]:
    """Return {button_id: [[answers], [answers], ...]} from the TOML config."""
    with open(path, "rb") as f:
        data = tomllib.load(f)

    buttons: dict[int, list[list[str]]] = {}
    for button in data.get("button", []):
        prompts = [p["answers"] for p in button.get("prompt", []) if p.get("answers")]
        if prompts:
            buttons[button["id"]] = prompts
    return buttons


def all_lines(buttons: dict[int, list[list[str]]]) -> list[str]:
    """Every unique answer string across all buttons, order preserved."""
    seen: set[str] = set()
    lines: list[str] = []
    for prompts in buttons.values():
        for answers in prompts:
            for text in answers:
                if text not in seen:
                    seen.add(text)
                    lines.append(text)
    return lines


def audio_filename(text: str) -> str:
    """Deterministic filename for a line: a readable slug plus a short hash."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")[:40] or "line"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}.mp3"
