"""The flame-topped robot: Claude's face on screen 2 and the companion on screen 3.

Drawn procedurally at any scale; every animation keeps the flame flickering so the screens feel alive.
Each animation is a list of 128x128 frames with info["duration"] set; the device loops the GIF itself.
"""
import math

from PIL import Image, ImageDraw

import style
from style import BG, mix

CREAM = (234, 216, 198)
CREAM_SH = (190, 168, 150)
VISOR = (10, 10, 14)
EAR = (110, 140, 190)
EAR_HI = (175, 205, 245)
GOLD = (217, 160, 40)
GOLD_HI = (255, 222, 120)
PINK = (244, 114, 182)
CORAL = (251, 113, 133)
EYE = (215, 235, 255)
GREEN = style.EMERALD
RED = style.RED
FLAME = (255, 150, 50)
FLAME_IN = (255, 225, 130)
YELLOW = style.AMBER
BLUE = style.VIOLET
LAPTOP = (70, 72, 82)
TEAR = style.SKY


class Pen:
    """Maps robot coordinates (a ~80x100 design grid) onto the screen at scale k."""

    def __init__(self, d, k, cx, top):
        self.d, self.k, self.cx, self.top = d, k, cx, top
        self.w = max(1, round(2 * k))

    def p(self, x, y):
        return (self.cx + x * self.k, self.top + y * self.k)

    def box(self, x0, y0, x1, y1):
        return (*self.p(x0, y0), *self.p(x1, y1))

    def r(self, r):
        return max(1, round(r * self.k))


def draw_robot(pen, i, eyes="open", eye_c=EYE, flame_c=FLAME, hands="rest", look=0, dim=False, gold=False):
    d, p, box = pen.d, pen.p, pen.box
    flick, sway = [0, 2, 1, 3][i % 4], [0, 1, 0, -1][i % 4]
    if dim:
        flick, flame_c = flick // 2 - 3, mix(flame_c, 0.6)
    inner = mix(FLAME_IN, 0.6) if dim else FLAME_IN

    # Flame with a soft glow.
    d.ellipse(box(-11, 3 - flick, 11, 25), fill=mix(flame_c, 0.12))
    d.ellipse(box(-8, 9, 8, 25), fill=flame_c)
    d.polygon([p(-7.5, 15), p(sway, 2 - flick), p(7.5, 15)], fill=flame_c)
    d.ellipse(box(-4, 15, 4, 24), fill=inner)
    d.polygon([p(-3.5, 18), p(sway, 10 - flick), p(3.5, 18)], fill=inner)

    # Body and side pods sit behind the head.
    if hands != "laptop":
        d.rounded_rectangle(box(-20, 68, 20, 94), radius=pen.r(10), fill=CREAM, outline=CREAM_SH)
    for s in (-1, 1):
        d.rounded_rectangle(box(s * 36 - 3.5, 36, s * 36 + 3.5, 58), radius=pen.r(3), fill=GOLD if gold else EAR)
        d.rectangle(box(s * 36 - 1, 40, s * 36 + 1, 54), fill=GOLD_HI if gold else EAR_HI)

    d.rounded_rectangle(box(-34, 20, 34, 74), radius=pen.r(18), fill=CREAM, outline=CREAM_SH)
    d.rounded_rectangle(box(-27, 28, 27, 66), radius=pen.r(12), fill=VISOR)

    for s in (-1, 1):
        x = s * 13 + look
        if eyes == "open" or (eyes == "half" and s == 1):
            d.rounded_rectangle(box(x - 3, 40, x + 3, 54), radius=pen.r(3), fill=eye_c)
        elif eyes == "down":
            d.rounded_rectangle(box(x - 3, 46, x + 3, 57), radius=pen.r(3), fill=eye_c)
        elif eyes == "blink":
            d.rectangle(box(x - 4, 47, x + 4, 48.5), fill=eye_c)
        elif eyes == "joy":
            d.line([p(x - 6, 51), p(x, 44), p(x + 6, 51)], fill=eye_c, width=pen.w)
        elif eyes == "closed":
            d.line([p(x - 6, 46), p(x, 51), p(x + 6, 46)], fill=eye_c, width=pen.w)
        elif eyes == "half":  # thinking squint on the left eye
            d.line([p(x - 6, 49), p(x + 5, 47)], fill=eye_c, width=pen.w)
        elif eyes == "angry":
            d.polygon([p(x - 6 * s, 42), p(x + 6 * s, 47), p(x + 5 * s, 53), p(x - 5 * s, 51)], fill=eye_c)
        elif eyes == "round":
            d.ellipse(box(x - 4, 43, x + 4, 52), fill=eye_c)
        elif eyes == "big":
            d.ellipse(box(x - 5, 41, x + 5, 54), fill=eye_c)
        elif eyes == "x":  # > <
            d.line([p(x + 5 * s, 42), p(x - 4 * s, 47), p(x + 5 * s, 52)], fill=eye_c, width=pen.w)
        elif eyes == "sad":
            d.rounded_rectangle(box(x - 3, 46, x + 3, 55), radius=pen.r(3), fill=eye_c)
            d.line([p(x - 5 * s, 40), p(x + 5 * s, 43)], fill=eye_c, width=pen.w)

    paw = lambda x, y: d.ellipse(box(x - 8, y - 7, x + 8, y + 7), fill=CREAM, outline=CREAM_SH)
    if hands in ("rest", "chin"):
        paw(-19, 90)
        paw(19, 90)
    if hands == "chin":
        paw(12, 66)
    elif hands == "laptop":
        d.rounded_rectangle(box(-30, 74, 24, 98), radius=pen.r(3), fill=LAPTOP)
        d.rectangle(box(-30, 74, 24, 76), fill=mix(EYE, 0.5))
        d.ellipse(box(-6, 83, 0, 89), fill=mix(EYE, 0.35))
        paw(26, 90 - 3 * (i % 2))
    elif hands == "up":
        paw(-38, 62 - 4 * (i % 2))
        paw(38, 62 - 4 * ((i + 1) % 2))
    elif isinstance(hands, int):  # waving: left hand raised, swinging by `hands` design units
        paw(19, 90)
        hx = -46 + hands
        d.line([p(-18, 78), p(hx, 54)], fill=CREAM_SH, width=pen.r(8))
        d.line([p(-18, 78), p(hx, 54)], fill=CREAM, width=pen.r(6))
        paw(hx, 50)


def ticks(pen, side, colour):
    """Two little burst dashes beside the head, like in the reference art."""
    d, p = pen.d, pen.p
    d.line([p(side * 36, 14), p(side * 43, 8)], fill=colour, width=pen.w)
    d.line([p(side * 26, 8), p(side * 28, 0)], fill=colour, width=pen.w)


def text(pen, x, y, s, colour):
    pen.d.text(pen.p(x, y), s, font=style.TEXT, fill=colour)


# name -> (frame count, ms per frame, function(i) -> (draw_robot kwargs, extras(pen, i), dx, dy))
ANIMATIONS = {
    "idle": (8, 260, lambda i: (dict(eyes="blink" if i == 6 else "open"), None, 0, (i // 2) % 2)),
    "happy": (6, 150, lambda i: (dict(eyes="joy"), lambda pen, i: i % 2 or ticks(pen, -1, YELLOW), 0, -(i % 2))),
    "success": (6, 150, lambda i: (dict(eyes="joy", eye_c=GREEN),
                                   lambda pen, i: i % 2 or ticks(pen, -1, GREEN), 0, -(i % 2))),
    "celebrate": (6, 120, lambda i: (dict(eyes="x", hands="up"), lambda pen, i: [ticks(pen, s, YELLOW)
                                     for s in (-1, 1)] if i % 2 == 0 else None, 0, -2 * (i % 2))),
    "working": (4, 200, lambda i: (dict(eyes="down", hands="laptop"), None, 0, 0)),
    "thinking": (8, 260, lambda i: (dict(eyes="half", hands="chin"),
                                    lambda pen, i: text(pen, 30, 2 - (i // 2) % 2 * 2, "?", BLUE), 0, 0)),
    "confused": (8, 260, lambda i: (dict(eyes="round", look=[-2, -2, 2, 2][i % 4]),
                                    lambda pen, i: text(pen, 32, 2 - (i // 2) % 2 * 2, "?", BLUE), 0, 0)),
    "error": (6, 110, lambda i: (dict(eyes="angry", eye_c=RED, flame_c=RED),
                                 lambda pen, i: [text(pen, -46, 4 + (i % 3), "+", RED),
                                                 text(pen, -38, -2 + (i % 2) * 2, "+", RED)], [-1, 1][i % 2], 0)),
    "offline": (8, 400, lambda i: (dict(eyes="closed", dim=True),
                                   lambda pen, i: [text(pen, 26 + t * 4, 14 - t * 6, "z", BLUE)
                                                   for t in range(1 + (i // 2) % 3)], 0, i // 4)),
    "wave": (4, 180, lambda i: (dict(eyes="joy", hands=[0, 6, 12, 6][i]), None, 0, 0)),
    "surprised": (6, 100, lambda i: (dict(eyes="big"), lambda pen, i: text(pen, 32, 2, "!", YELLOW),
                                     [-2, 2, -2, 2, 0, 0][i], 0)),
    "sad": (6, 250, lambda i: (dict(eyes="sad", dim=True),
                               lambda pen, i: pen.d.ellipse(pen.box(-17, 56 + i * 4, -13, 61 + i * 4), fill=TEAR),
                               0, 1)),
}


# The companion grows with Claude's finished turns (see state.level): (level, unlock).
UNLOCKS = ((2, "румянец"), (3, "золотые наушники"), (5, "шарф"), (7, "значок"), (10, "сияние"))


def accessories(pen, i, level):
    d, p, box = pen.d, pen.p, pen.box
    if level >= 2:
        for s in (-1, 1):
            d.rectangle(box(s * 21 - 3, 57, s * 21 + 3, 59), fill=mix(PINK, 0.7))
    if level >= 5:
        d.rounded_rectangle(box(-22, 69, 22, 77), radius=pen.r(4), fill=CORAL)
        d.rounded_rectangle(box(9, 73, 16, 88), radius=pen.r(3), fill=CORAL)
    if level >= 7:
        cx, cy, r = -8, 84, 4.5
        d.polygon([p(cx + r * (1 if n % 2 == 0 else 0.45) * math.sin(n * 0.6283),
                     cy - r * (1 if n % 2 == 0 else 0.45) * math.cos(n * 0.6283)) for n in range(10)],
                  fill=GOLD_HI)
    if level >= 10:
        for k, (x, y) in enumerate([(-44, 30), (44, 36), (-40, 70), (42, 66)]):
            if (i + k) % 2 == 0:
                d.line([p(x - 3, y), p(x + 3, y)], fill=GOLD_HI)
                d.line([p(x, y - 3), p(x, y + 3)], fill=GOLD_HI)


def animate(name, k, cx, top, background=None, level=1):
    """Frames of animation `name` at scale k; `background(i)` returns (image, draw) to draw onto.
    `level` dresses the robot with what it has unlocked (the companion only)."""
    count, ms, pose = ANIMATIONS[name]
    out = []
    for i in range(count):
        kwargs, extras, dx, dy = pose(i)
        if background:
            img, d = background(i)
        else:
            img = Image.new("RGB", (128, 128), BG)
            d = ImageDraw.Draw(img)
            d.fontmode = "1"
        pen = Pen(d, k, cx + dx, top + dy)
        draw_robot(pen, i, gold=level >= 3, **kwargs)
        accessories(pen, i, level)
        if extras:
            extras(pen, i)
        img.info["duration"] = ms
        out.append(img)
    return out


# Companion emotions (screen 3) -> animation, label colour, label.
EMOTIONS = {
    "neutral": ("idle", EYE, ""),
    "happy": ("success", GREEN, "ура!"),
    "proud": ("celebrate", YELLOW, "супер!"),
    "waving": ("wave", style.AMBER, "← эй!"),
    "bored": ("offline", style.SLATE, ""),
    "surprised": ("surprised", RED, "ой!"),
    "sad": ("sad", TEAR, "эх…"),
}
# Claude statuses (screen 2) -> animation.
STATUSES = {
    "idle": "idle",
    "thinking": "thinking",
    "working": "working",
    "waiting_for_user": "confused",
    "done": "happy",
    "error": "error",
}


def label(img, text, colour):
    """Companion caption under the robot, large enough to read across the desk."""
    if text:
        d = ImageDraw.Draw(img)
        d.fontmode = "1"
        d.text((64, 100), text, font=style.TEXT2, fill=colour, anchor="ma")


def frames(emotion: str, label_it: bool = True, level: int = 1) -> list:
    name, colour, text = EMOTIONS[emotion]
    out = animate(name, 0.85, 64, 12, level=level)
    if label_it:
        for img in out:
            label(img, text, colour)
    return out
