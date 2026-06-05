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


def load_button_labels(path: str = CONFIG_PATH) -> dict[int, str]:
    """Return {button_id: "name / name"} from the prompt names in the TOML config.

    Each prompt carries a human-readable "name"; this joins a button's prompt names
    so the UI can label the button with what it does. Buttons whose prompts have no
    names are omitted, letting callers fall back to a generic label.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    labels: dict[int, str] = {}
    for button in data.get("button", []):
        names = [p["name"] for p in button.get("prompt", []) if p.get("name")]
        if names:
            labels[button["id"]] = " / ".join(names)
    return labels


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
