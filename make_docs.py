"""Regenerates the README pictures in docs/ from example data (no device, no real sessions needed).

Usage: python3 make_docs.py
"""
import json
import os
import tempfile
import time
from pathlib import Path

os.environ.pop("CLAUDE_CODE_USER_EMAIL", None)  # example data only, never the account running this

import limits
import render
import robot
import state
from PIL import Image

OUT = Path(__file__).parent / "docs"
ME = "you@example.com"


def strip(images, name, scale=3, gap=6):
    sheet = Image.new("RGB", (len(images) * (128 + gap) - gap, 128), (0, 0, 0))
    for i, f in enumerate(images):
        sheet.paste(f, (i * (128 + gap), 0))
    sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST).save(OUT / f"{name}.png", optimize=True)


def gif(frames, name, scale=3):
    big = [f.resize((128 * scale, 128 * scale), Image.NEAREST) for f in frames]
    big[0].save(OUT / f"{name}.gif", save_all=True, append_images=big[1:], loop=0,
                duration=[f.info.get("duration", 200) for f in frames])


def main():
    OUT.mkdir(exist_ok=True)
    state.DATA = Path(tempfile.mkdtemp())
    state.PATH = state.DATA / "state.json"
    limits.PATH = state.DATA / "limits.json"
    now = time.time()
    limits.PATH.write_text(json.dumps({"at": now, "accounts": {ME: {
        "at": now, "label": "работа", "history": [[now - 3600, 34], [now, 64]],
        "five_hour": {"used_percentage": 64, "resets_at": now + 7400},
        "seven_day": {"used_percentage": 38, "resets_at": now + 3 * 86400}}}}))
    hour = time.localtime().tm_hour
    state.PATH.write_text(json.dumps({**state.empty(), "done_total": 64, "last_event": now, "account": ME,
        "busy_hours": {str(max(0, hour - k)): v for k, v in [(1, 3000), (2, 2400), (3, 1800), (4, 3600), (6, 1200)]}}))

    state.update_session("a", "api-server", "working", account=ME)
    state.update_session("b", "website", "waiting_for_user", "Bash", account=ME)
    with state.mutate() as s:
        s["companion"]["until"] = 0
    screens = render.render_all(state.load())
    for i, frames in enumerate(screens):
        gif(frames, f"gate-{i + 1}")
    strip([f[0] for f in screens], "gate")

    for sid in ("a", "b"):
        state.end_session(sid)
    strip([f[0] for f in render.render_all(state.load())], "gate-idle")

    statuses = ("working", "thinking", "waiting_for_user", "done", "working", "error")
    strip([render.session_screen({"name": "api-server", "status": st, "since": now - 1500, "text": "Edit", "look": n})[1]
           for n, st in enumerate(statuses)], "office")
    strip([render.session_screen({"name": "website", "status": "waiting_for_user", "since": now - 400, "text": t,
                                  "look": 2})[0] for t in ("Bash", "Edit", "Read", "WebFetch", "Agent", "mcp__x")],
          "badges")
    strip([robot.frames("neutral", level=lvl)[0] for lvl in (1, 2, 3, 5, 7, 10)], "levels")
    print("docs/ updated")


if __name__ == "__main__":
    main()
