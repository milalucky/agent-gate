"""One palette and type scale for every screen (dark slate + Tailwind 400 status hues, per the design system).

Pixel fonts only render crisply at whole multiples of their grid: Ark Pixel at 12/24, Departure Mono at 11/22/33.
"""
from pathlib import Path

from PIL import ImageFont

_FONTS = Path(__file__).parent / "fonts"
TEXT = ImageFont.truetype(str(_FONTS / "ArkPixel12.otf"), 12)  # labels, Cyrillic
TEXT2 = ImageFont.truetype(str(_FONTS / "ArkPixel12.otf"), 24)
NUM = ImageFont.truetype(str(_FONTS / "DepartureMono.otf"), 22)  # figures
NUM3 = ImageFont.truetype(str(_FONTS / "DepartureMono.otf"), 33)

BG = (11, 16, 32)
CARD = (22, 30, 49)
EDGE = (36, 46, 70)
FG = (241, 245, 249)
MUTED = (148, 163, 184)
FAINT = (71, 85, 105)

VIOLET = (167, 139, 250)
SKY = (56, 189, 248)
AMBER = (251, 191, 36)
EMERALD = (52, 211, 153)
RED = (248, 113, 113)
SLATE = (100, 116, 139)
ORANGE = (251, 146, 60)

STATUS = {  # label, colour
    "idle": ("ожидает", SLATE),
    "thinking": ("думает", VIOLET),
    "working": ("работает", SKY),
    "waiting_for_user": ("ждёт тебя", AMBER),
    "done": ("готово", EMERALD),
    "error": ("ошибка", RED),
}


def mix(c, k, base=BG):
    """Blend a colour towards the background: glows and dimmed states."""
    return tuple(int(b + (a - b) * k) for a, b in zip(c, base))
