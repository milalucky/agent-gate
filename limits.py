"""Claude rate limits for the dashboard, from Claude Code's own /usage command, for whichever account is active.

/usage costs no tokens and shows exactly what the usage screen shows. Claude Code follows the account
picked in the Claude app, so each refresh also asks `claude auth status` who is logged in: limits and
the sessions shown on the gate both follow an account switch. No user settings are loaded, so our own
hooks don't fire and no phantom session appears; no transcript is saved.
"""
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
PATH = DATA / "limits.json"
# launchd starts the daemon with a bare PATH, so look in the native installer's folder too.
CLAUDE = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
USAGE = [CLAUDE, "-p", "/usage", "--output-format", "json", "--setting-sources", "", "--strict-mcp-config",
         "--no-session-persistence"]
WINDOWS = {"session": "five_hour", "week (all models)": "seven_day"}
LINE = re.compile(r"Current (session|week \(all models\)): (\d+(?:\.\d+)?)% used(?: · resets (\w{3} \d+) at (\d+(?::\d+)?[ap]m))?")


def reset_time(day: str, clock: str, now: datetime) -> float:
    """'Oct 27' + '3:50pm' in local time -> timestamp; a date that already passed means next year."""
    fmt = "%b %d %Y %I:%M%p" if ":" in clock else "%b %d %Y %I%p"
    when = datetime.strptime(f"{day} {now.year} {clock}", fmt)
    if when < now.replace(tzinfo=None) and (now.replace(tzinfo=None) - when).days > 1:
        when = when.replace(year=now.year + 1)
    return when.timestamp()


def parse(text: str, now: datetime = None) -> dict:
    now = now or datetime.now()
    out = {}
    for name, used, day, clock in LINE.findall(text):
        out[WINDOWS[name]] = {"used_percentage": float(used), "resets_at": reset_time(day, clock, now) if day else None}
    return out


def config_dirs() -> list:
    """Claude Code config folders to read limits from, one per logged-in account (.env CLAUDE_CONFIG_DIRS,
    colon-separated). The default ~/.claude is always included; add e.g. ~/.claude-personal after
    `CLAUDE_CONFIG_DIR=~/.claude-personal claude auth login` to see a second account's limits."""
    env_file = DATA.parent / ".env"
    extra = ""
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("CLAUDE_CONFIG_DIRS="):
                extra = line.split("=", 1)[1].strip()
    return [None] + [os.path.expanduser(d) for d in extra.split(":") if d.strip()]


def _run(args, config_dir):
    env = dict(os.environ)
    env.pop("CLAUDE_CONFIG_DIR", None)
    if config_dir:  # the default folder is left unset: its login lives under a different keychain name
        env["CLAUDE_CONFIG_DIR"] = config_dir
    return subprocess.run([CLAUDE, *args], capture_output=True, text=True, timeout=120, cwd=str(DATA), env=env)


def account(config_dir=None) -> dict:
    """Who that config folder is logged in as; a team or enterprise seat counts as work."""
    info = json.loads(_run(["auth", "status"], config_dir).stdout)
    work = info.get("subscriptionType") in ("team", "enterprise")
    return {"email": info.get("email") or "", "label": "работа" if work else "личный"}


def refresh() -> dict:
    """Limits of every logged-in account, keyed by email."""
    old = load().get("accounts", {})
    accounts = {}
    for config_dir in config_dirs():
        try:
            who = account(config_dir)
            run = _run(USAGE[1:], config_dir)
            windows = parse(json.loads(run.stdout or "{}").get("result", ""))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
        if who["email"] and windows:
            data = {"at": time.time(), **windows, "label": who["label"]}
            data["history"] = history(old.get(who["email"], {}), data)
            accounts[who["email"]] = data
    if not accounts:
        raise RuntimeError("/usage gave no limits for any account")
    out = {"at": time.time(), "accounts": {**old, **accounts}}
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False))
    os.replace(tmp, PATH)
    return out


def history(old: dict, data: dict) -> list:
    """Recent (time, used %) samples of the current 5-hour window, for the burn-rate forecast."""
    five_hour = data.get("five_hour")
    if not five_hour:
        return []
    same = (old.get("five_hour") or {}).get("resets_at") == five_hour.get("resets_at")
    now = time.time()
    samples = [s for s in old.get("history", []) if same and now - s[0] < 2 * 3600]
    return samples + [[now, five_hour["used_percentage"]]]


def forecast(data: dict):
    """Seconds until the 5-hour limit runs out at the recent pace, or None if it won't before reset."""
    samples, window = data.get("history") or [], data.get("five_hour") or {}
    if len(samples) < 2 or samples[-1][0] - samples[0][0] < 20 * 60:
        return None
    rate = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
    if rate <= 0:
        return None
    left = (100 - samples[-1][1]) / rate - (time.time() - samples[-1][0])
    reset = window.get("resets_at") or float("inf")
    return max(0, left) if time.time() + left < reset else None


def load() -> dict:
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}


def for_account(email):
    """Limits of that account, or of the only known one when the gate doesn't know the account yet."""
    accounts = load().get("accounts", {})
    if email:
        return accounts.get(email)
    return next(iter(accounts.values()), None) if len(accounts) == 1 else None


def age() -> float:
    return time.time() - load().get("at", float("-inf"))


if __name__ == "__main__":
    print(refresh())
