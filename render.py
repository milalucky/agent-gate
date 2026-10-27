"""Draws the five 128x128 screens: Claude sessions next to the companion, widgets on the free screens.

Every screen keeps a few large words: Ark Pixel for Cyrillic labels, Departure Mono for figures.
"""
import time

from PIL import Image, ImageDraw, ImageOps

import limits
import robot
import state
import style
from style import BG, CARD, EDGE, FAINT, FG, MUTED, NUM, NUM3, TEXT, TEXT2

POINT_AT_DONE_FOR = 2 * 60  # a finished session gets pointed at briefly, then the dispatcher moves on
BORED_AFTER = 30 * 60
LIMITS_FRESH = 15 * 60  # older limits get their age in the card title


def canvas():
    img = Image.new("RGB", (128, 128), BG)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"  # hard pixel edges, no anti-aliasing
    return img, d


def fit(text: str, font, width: int = 120) -> str:
    """Trim text with an ellipsis until it fits the width in pixels."""
    if font.getlength(text) <= width:
        return text
    while text and font.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(text: str, font, width: int = 120) -> list:
    rows, row = [], ""
    for word in text.split():
        trial = f"{row} {word}".strip()
        if font.getlength(trial) <= width or not row:
            row = trial
        else:
            rows.append(row)
            row = word
    return rows + [row] if row else rows


def card(d, title: str, right: str = "", dot=None):
    """A rounded card filling the screen, with a small title row."""
    d.rounded_rectangle((2, 2, 125, 125), radius=10, fill=CARD, outline=EDGE)
    x = 10
    if dot:
        d.ellipse((10, 9, 15, 14), fill=dot)
        x = 19
    d.text((x, 6), title, font=TEXT, fill=MUTED)
    if right:
        d.text((118, 6), right, font=TEXT, fill=MUTED, anchor="ra")


def duration(seconds: float) -> str:
    """Coarse on purpose: every change of a screen costs a loading animation on the device,
    so labels move in 5-minute steps, then half hours, then hours."""
    m = int(seconds // 60)
    if m < 5:
        return "<5м"
    if m < 60:
        return f"{m // 5 * 5}м"
    if m < 10 * 60:
        return f"{m // 60}ч{m % 60 // 30 * 30:02d}" if m % 60 >= 30 else f"{m // 60}ч"
    if m < 24 * 60:
        return f"{m // 60}ч"
    return f"{m // 1440}д{m % 1440 // 60}ч"


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


# --- sessions ---

TOOL_KIND = {"Bash": "term", "BashOutput": "term", "KillShell": "term", "Edit": "edit", "Write": "edit",
             "MultiEdit": "edit", "NotebookEdit": "edit", "Read": "find", "Grep": "find", "Glob": "find",
             "WebFetch": "web", "WebSearch": "web", "Task": "agent", "Agent": "agent"}


def tool_badge(d, tool: str, colour):
    """What a waiting session asks permission for, as a pixel icon in a badge beside the robot."""
    kind = TOOL_KIND.get(tool, "plug" if tool.startswith("mcp__") else None)
    if not kind:
        return
    cx, cy = 98, 30  # right over the robot's "?": the badge is the question
    d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=style.mix(colour, 0.25), outline=style.mix(colour, 0.7))
    if kind == "term":
        d.rectangle((cx - 7, cy - 5, cx + 7, cy + 5), outline=colour)
        d.line((cx - 4, cy - 2, cx - 1, cy, cx - 4, cy + 2), fill=colour)
        d.line((cx + 1, cy + 2, cx + 4, cy + 2), fill=colour)
    elif kind == "edit":
        d.line((cx - 5, cy + 5, cx + 4, cy - 4), fill=colour, width=3)
        d.point((cx - 6, cy + 6), fill=FG)
    elif kind == "find":
        d.ellipse((cx - 6, cy - 6, cx + 2, cy + 2), outline=colour, width=2)
        d.line((cx + 2, cy + 2, cx + 6, cy + 6), fill=colour, width=2)
    elif kind == "web":
        d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=colour)
        d.ellipse((cx - 3, cy - 7, cx + 3, cy + 7), outline=colour)
        d.line((cx - 7, cy, cx + 7, cy), fill=colour)
    elif kind == "agent":
        d.rounded_rectangle((cx - 7, cy - 4, cx - 1, cy + 2), radius=2, outline=colour)
        d.rounded_rectangle((cx + 1, cy - 1, cx + 7, cy + 5), radius=2, fill=colour)
    else:  # plug: an MCP tool
        d.line((cx - 3, cy - 7, cx - 3, cy - 3), fill=colour, width=2)
        d.line((cx + 2, cy - 7, cx + 2, cy - 3), fill=colour, width=2)
        d.rounded_rectangle((cx - 6, cy - 3, cx + 5, cy + 3), radius=2, fill=colour)
        d.line((cx, cy + 3, cx, cy + 7), fill=colour, width=2)

def session_screen(sess: dict) -> list:
    status = sess["status"]
    label, colour = style.STATUS[status]
    name = fit(sess["name"], TEXT)
    timer = "" if status == "idle" else duration(time.time() - sess["since"])

    def background(i):
        img, d = canvas()
        d.text((64, 3), name, font=TEXT, fill=FG, anchor="ma")
        d.rounded_rectangle((6, 98, 121, 123), radius=8, fill=style.mix(colour, 0.18), outline=style.mix(colour, 0.5))
        d.text((13, 104), label, font=TEXT, fill=colour)
        d.text((115, 104), timer, font=TEXT, fill=FG, anchor="ra")
        return img, d

    frames = robot.animate(robot.STATUSES[status], 0.74, 64, 20, background)
    if status == "waiting_for_user":
        for f in frames:  # after the robot, so the badge covers its "?"
            tool_badge(ImageDraw.Draw(f), sess.get("text", ""), colour)
    return frames


# --- companion ---

def companion_emotion(s: dict):
    """(emotion, side). The dispatcher waves only when a session needs you, otherwise it watches the
    working ones; side is -1/1 for the screens left/right of it."""
    now = time.time()
    c = s["companion"]
    live = state.live_sessions(s)
    waiting = [n for n, x in live.items() if x["status"] == "waiting_for_user"]
    fresh_done = [n for n, x in live.items() if x["status"] == "done" and now - x["since"] < POINT_AT_DONE_FOR]
    busy = {-1 if n < 3 else 1 for n, x in live.items() if x["status"] in state.BUSY}
    target = (waiting or fresh_done or [None])[0]
    side = -1 if target is None or target < 3 else 1
    if now < c["until"]:
        return c["emotion"], side
    if target is not None:
        return "waving", side
    if len(busy) == 2:
        return "scanning", 0
    if busy:
        return "watching", busy.pop()
    if now - s["last_event"] > BORED_AFTER:
        return "bored", side
    return "neutral", side


SUMMARY = (("waiting_for_user", style.AMBER), ("busy", style.SKY), ("done", style.EMERALD), ("error", style.RED))


def summary_bar(d, live: dict):
    """The dispatcher's board: how many sessions wait for you, work, are done, failed. Dot + number each."""
    counts = {}
    for x in live.values():
        key = "busy" if x["status"] in state.BUSY else x["status"]
        counts[key] = counts.get(key, 0) + 1
    items = [(counts[k], colour) for k, colour in SUMMARY if counts.get(k)]
    width = sum(10 + NUM.getlength(str(n)) for n, _ in items) + 10 * (len(items) - 1)
    x = 64 - width / 2
    for n, colour in items:
        d.ellipse((x, 110, x + 7, 117), fill=colour)
        d.text((x + 10, 102), str(n), font=NUM, fill=colour)
        x += 10 + NUM.getlength(str(n)) + 10


def companion_screen(s: dict) -> list:
    emotion, side = companion_emotion(s)
    frames = robot.frames(emotion, label_it=False, level=state.level(s["done_total"])[0])
    if emotion in ("waving", "watching") and side == 1:
        frames = [ImageOps.mirror(f) for f in frames]  # the robot is symmetric, only the gesture flips
    _, colour, label = robot.EMOTIONS[emotion]
    if emotion == "waving":
        label = "← эй!" if side == -1 else "эй! →"
    live = state.live_sessions(s)
    for f in frames:
        if label:
            robot.label(f, label, colour)
        elif live:
            d = ImageDraw.Draw(f)
            d.fontmode = "1"
            summary_bar(d, live)
    return frames


# --- widgets for free screens ---

def gauge_colour(used: float):
    return style.EMERALD if used < 60 else style.AMBER if used < 85 else style.RED


def limit_screen(title: str, window: dict, data: dict) -> list:
    """Ring gauge of how much of a rate-limit window is used, with time to reset.

    Old data shows its age in the title; a window whose reset time has passed counts as empty again.
    """
    age = time.time() - data.get("at", 0)
    img, d = canvas()
    card(d, title, f"{duration(age)} назад" if window and age > LIMITS_FRESH else data.get("label", ""))
    box = (24, 26, 104, 106)
    d.arc(box, 135, 405, fill=EDGE, width=7)
    used = window.get("used_percentage", window.get("utilization"))
    reset = window.get("resets_at")
    if isinstance(reset, (int, float)) and reset <= time.time():
        d.text((64, 52), "0%", font=NUM, fill=FG, anchor="ma")
        d.text((64, 108), "сброшен", font=TEXT, fill=MUTED, anchor="ma")
    elif isinstance(used, (int, float)):
        colour = gauge_colour(used)
        if used > 0:
            d.arc(box, 135, 135 + 270 * min(used, 100) / 100, fill=colour, width=7)
        d.text((64, 52), f"{round(used)}%", font=NUM, fill=FG, anchor="ma")
        runs_out = limits.forecast(data) if title == "5 часов" else None
        if runs_out is not None:  # at this pace the limit ends before it resets
            d.text((64, 108), f"хватит на {duration(runs_out)}", font=TEXT, fill=colour, anchor="ma")
        elif isinstance(reset, (int, float)):
            d.text((64, 108), f"сброс {duration(max(0, reset - time.time()))}", font=TEXT, fill=MUTED, anchor="ma")
    else:
        d.text((64, 52), "нет данных", font=TEXT, fill=FAINT, anchor="ma")
        if not data:  # this account isn't logged in for Claude Code, see README "Second account"
            d.text((64, 108), "войди в claude", font=TEXT, fill=MUTED, anchor="ma")
    return [img]


def five_hour_screen(s: dict) -> list:
    data = limits.for_account(s.get("account")) or {}
    return limit_screen("5 часов", data.get("five_hour") or {}, data)


def week_screen(s: dict) -> list:
    data = limits.for_account(s.get("account")) or {}
    return limit_screen("неделя", data.get("seven_day") or {}, data)


def activity_screen(s: dict) -> list:
    """Claude's busy time per hour over the last 12 hours."""
    busy = state.busy_hours(s)
    hour = time.localtime().tm_hour
    img, d = canvas()
    card(d, "работа", duration(sum(busy.values()) // 600 * 600))
    for i in range(12):
        h = hour - 11 + i
        # shortcut: hours before midnight show as empty, the per-hour log resets with the day
        secs = busy.get(str(h), 0) // 600 * 600 if h >= 0 else 0  # 10-minute steps, fewer redraws
        x = 10 + i * 9
        d.rounded_rectangle((x, 30, x + 6, 104), radius=3, fill=style.mix(EDGE, 0.7))
        top = 104 - round(74 * min(secs, 3600) / 3600)
        if top < 102:
            d.rounded_rectangle((x, top, x + 6, 104), radius=3, fill=style.AMBER if i == 11 else style.SKY)
        if h % 3 == 0 and h >= 0:
            d.text((x + 3, 108), str(h), font=TEXT, fill=MUTED, anchor="ma")
    return [img]


def level_screen(s: dict) -> list:
    """Changes only when the bar grows a fifth or the level goes up, not on every finished answer."""
    lvl, into, need = state.level(s["done_total"])
    fifths = into * 5 // need
    img, d = canvas()
    card(d, "уровень", dot=style.ORANGE)
    d.text((64, 24), str(lvl), font=NUM3, fill=style.ORANGE, anchor="ma")
    for k in range(5):
        x = 12 + k * 21
        d.rounded_rectangle((x, 72, x + 18, 80), radius=3, fill=style.ORANGE if k < fifths else style.mix(EDGE, 0.7))
    upcoming = [(at, what) for at, what in robot.UNLOCKS if at > lvl]
    if upcoming:
        d.text((64, 92), f"ур.{upcoming[0][0]}", font=TEXT, fill=MUTED, anchor="ma")
        d.text((64, 106), upcoming[0][1], font=TEXT, fill=FG, anchor="ma")
    return [img]


WIDGETS = (five_hour_screen, week_screen, activity_screen, level_screen)  # fill free screens left to right


def overlay_screen(text: str) -> Image.Image:
    img, d = canvas()
    d.rounded_rectangle((2, 2, 125, 125), radius=10, fill=CARD, outline=style.AMBER)
    rows = wrap(text, TEXT2, 112)[:4]
    y = 64 - len(rows) * 26 // 2
    for row in rows:
        d.text((64, y), fit(row, TEXT2, 112), font=TEXT2, fill=FG, anchor="ma")
        y += 26
    return img


def render_all(s: dict) -> list:
    """Five frame lists: one frame for a still screen, several for an animation."""
    live = state.live_sessions(s)
    widgets = iter(WIDGETS)
    out = []
    for n in range(1, 6):
        o = s["overlays"].get(str(n))
        if o and time.time() < o["until"]:
            out.append([overlay_screen(o["text"])])
        elif n == 3:
            out.append(companion_screen(s))
        elif n in live:
            out.append(session_screen(live[n]))
        else:
            out.append(next(widgets)(s))
    return out
