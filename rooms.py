"""The office: a different corner behind every session's robot, so screens never look alike.

Each corner keeps to the sides (x < 34 or x > 94) and the floor, leaving the middle to the robot, and is drawn
in muted colours so the robot stays the brightest thing on the screen. Small details move with the frame
index `i` (server lights, steam, city windows), so a corner is alive even while its robot sits still.
"""
from style import mix

FLOOR = (34, 30, 46)
FLOOR_LINE = (52, 46, 66)
NAMES = ("city", "library", "servers", "garden", "board", "cafe")


def floor(d):
    d.rectangle((0, 92, 127, 97), fill=FLOOR)
    d.line((0, 92, 127, 92), fill=FLOOR_LINE)


def city(d, i):
    """A night window with a skyline whose windows switch on and off."""
    d.rectangle((4, 20, 32, 58), fill=(18, 24, 52), outline=(70, 76, 104))
    d.line((18, 20, 18, 58), fill=(70, 76, 104))
    for x, h in ((6, 18), (11, 26), (20, 14), (25, 22)):
        d.rectangle((x, 57 - h, x + 4, 57), fill=(40, 46, 78))
        for k, y in enumerate(range(59 - h, 56, 4)):
            if (x + y + i) % 3:
                d.point((x + 2, y), fill=(250, 204, 21) if (x + k + i // 2) % 4 == 0 else (90, 90, 70))
    d.point((28, 24), fill=(241, 245, 249))  # a star


def library(d, i):
    """A bookshelf on the right."""
    d.rectangle((97, 20, 124, 91), fill=(46, 34, 30), outline=(74, 56, 46))
    colours = [(167, 139, 250), (56, 189, 248), (251, 146, 60), (52, 211, 153), (248, 113, 113), (251, 191, 36)]
    for row, y in enumerate((24, 46, 68)):
        d.line((97, y + 19, 124, y + 19), fill=(74, 56, 46))
        x = 99
        for k in range(6):
            w = 3 + (row + k) % 2
            top = y + 4 + (k * 5 + row) % 6
            d.rectangle((x, top, x + w - 1, y + 18), fill=mix(colours[(k + row * 2) % 6], 0.55))
            x += w + 1


def servers(d, i):
    """A server rack with blinking lights."""
    d.rectangle((4, 18, 30, 91), fill=(30, 34, 44), outline=(60, 66, 82))
    for k, y in enumerate(range(22, 88, 8)):
        d.rectangle((7, y, 27, y + 5), fill=(42, 48, 62))
        on = (k * 7 + i) % 5
        d.point((10, y + 2), fill=(52, 211, 153) if on else (24, 60, 50))
        d.point((13, y + 2), fill=(251, 191, 36) if (k + i) % 3 == 0 else (60, 52, 30))
        d.line((18, y + 2, 24, y + 2), fill=(70, 78, 96))


def garden(d, i):
    """A sunny window and a potted plant."""
    d.rectangle((96, 20, 124, 52), fill=(30, 58, 92), outline=(70, 96, 124))
    d.ellipse((103, 25, 113, 35), fill=(251, 191, 36))
    cx = 98 + (i % 8)  # a cloud drifting by
    d.ellipse((cx, 40, cx + 10, 46), fill=(200, 214, 230))
    d.rectangle((10, 80, 24, 91), fill=(160, 90, 60))
    for dx, dy in ((-4, -6), (0, -12), (4, -7), (-1, -18), (3, -15)):
        d.ellipse((15 + dx, 76 + dy, 19 + dx, 82 + dy), fill=(52, 160, 100))


def board(d, i):
    """A whiteboard with scribbles and sticky notes."""
    d.rectangle((94, 18, 124, 52), fill=(214, 220, 228), outline=(120, 128, 140))
    for y, w in ((24, 18), (29, 12), (34, 20), (39, 9)):
        d.line((98, y, 98 + w, y), fill=(56, 92, 170))
    d.rectangle((112, 40, 119, 47), fill=(251, 191, 36))
    d.rectangle((103, 42, 109, 48), fill=(244, 114, 182))
    d.line((94, 53, 94, 91), fill=(90, 96, 110))
    d.line((124, 53, 124, 91), fill=(90, 96, 110))


def cafe(d, i):
    """A coffee machine with rising steam."""
    d.rectangle((6, 54, 28, 91), fill=(60, 64, 76), outline=(90, 96, 110))
    d.rectangle((10, 58, 24, 66), fill=(30, 34, 44))
    d.point((12, 62), fill=(52, 211, 153))
    d.rectangle((13, 78, 21, 86), fill=(241, 245, 249))
    d.rectangle((21, 80, 23, 84), outline=(241, 245, 249))
    for k in range(3):
        y = 74 - ((i * 2 + k * 4) % 12)
        d.point((15 + k * 2 + (y % 2), y), fill=(150, 160, 180))


DRAW = {"city": city, "library": library, "servers": servers, "garden": garden, "board": board, "cafe": cafe}


def draw(d, name: str, i: int):
    floor(d)
    DRAW[name](d, i)
