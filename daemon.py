"""Dashboard daemon: renders the five screens every second and sends only the ones that changed.

Usage: python3 daemon.py   (normally started by launchd, see com.timesgate.daemon.plist)
"""
import hashlib
import logging
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

import limits
import render
import state
from device import Device, DeviceError

TICK = 1
PANEL_PAUSE = 0.5
# A rebooting device needs its cloud handshake before the local API works again.
RETRY_AFTER = 60
# Shorter than a reboot (power-up plus cloud handshake), so a power cycle is never missed.
HEARTBEAT = 15
SETTLE = 3
NIGHT = (23, 7)  # local hours: dim the screens from 23:00 to 07:00
BRIGHTNESS = {"day": 100, "night": 25}
LIMITS_EVERY = 2 * 60  # /usage is free; often enough to follow an account switch in the app
LIMITS_IDLE_EVERY = 30 * 60
ACTIVE_FOR = 30 * 60

log = logging.getLogger("timesgate")


def setup_logging():
    state.DATA.mkdir(exist_ok=True)
    handlers = [RotatingFileHandler(state.DATA / "daemon.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")]
    if sys.stderr.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=handlers)


def limits_loop():
    """Refreshes Claude's rate limits in the background; a slow or failed call never stalls the screens."""
    while True:
        try:
            active = time.time() - state.load()["last_event"] < ACTIVE_FOR
            if limits.age() > (LIMITS_EVERY if active else LIMITS_IDLE_EVERY):
                data = limits.refresh()
                for email, acc in data["accounts"].items():
                    log.info("limits %s: 5h %s%% week %s%%", acc.get("label"),
                             acc.get("five_hour", {}).get("used_percentage"), acc.get("seven_day", {}).get("used_percentage"))
        except Exception as exc:
            log.warning("limits refresh failed: %s", exc)
        time.sleep(60)


def run():
    setup_logging()
    device = Device()
    sent = [None] * 5
    seen, seen_at = [None] * 5, [0.0] * 5
    brightness = None
    retry_at = beat_at = 0
    threading.Thread(target=limits_loop, daemon=True).start()
    error = None
    log.info("daemon started, device %s", device.ip)
    while True:
        try:
            s = state.load()
            if s["day"] != state.today():
                with state.mutate():
                    pass  # mutate() performs the day rollover
                continue
            if time.time() >= retry_at:
                try:
                    # A power-cycled device comes back on its stock screens; only a miss here tells us.
                    if time.time() - beat_at > HEARTBEAT:
                        device.command({"Command": "Channel/GetAllConf"})
                        beat_at = time.time()
                    hour = time.localtime().tm_hour
                    level = BRIGHTNESS["night" if hour >= NIGHT[0] or hour < NIGHT[1] else "day"]
                    if level != brightness:
                        device.command({"Command": "Channel/SetBrightness", "Brightness": level})
                        brightness = level
                        log.info("brightness %s", level)
                    for i, frames in enumerate(render.render_all(s)):
                        digest = hashlib.sha1(b"".join(f.tobytes() for f in frames)).hexdigest()
                        if digest == sent[i]:
                            continue
                        if digest != seen[i]:
                            seen[i], seen_at[i] = digest, time.time()
                        # Let a changing screen settle first: thinking -> working within seconds is one
                        # loading animation on the device, not two. First sends (start, reboot) go at once.
                        if sent[i] is not None and time.time() - seen_at[i] < SETTLE:
                            continue
                        device.show(i, frames)
                        sent[i] = digest
                        log.info("screen %d updated", i + 1)
                        time.sleep(PANEL_PAUSE)
                    error = None
                except DeviceError as exc:
                    log.warning("%s; retry in %ss", exc, RETRY_AFTER)
                    sent = [None] * 5  # the device may have rebooted: resend everything
                    brightness = None
                    try:
                        if device.rediscover():
                            log.info("gate found at a new address %s", device.ip)
                            retry_at = 0  # try it right away
                            continue
                    except (OSError, DeviceError) as lookup_error:
                        log.warning("gate lookup failed: %s", lookup_error)
                    retry_at = time.time() + RETRY_AFTER
                    error = str(exc)
            state.write_health(error)
        except Exception:  # a bad state file or a render bug must not stop the dashboard
            log.exception("unexpected error, retry in %ss", RETRY_AFTER)
            time.sleep(RETRY_AFTER)
        time.sleep(TICK)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
