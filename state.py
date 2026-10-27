"""Dashboard state in data/state.json, shared by the daemon, the CLI, the MCP server and the hook.

Writers take an flock and replace the file atomically, so the daemon can read without locking.
"""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path


DATA = Path(__file__).parent / "data"
PATH = DATA / "state.json"

STATUSES = ("idle", "thinking", "working", "waiting_for_user", "done", "error")
EMOTIONS = ("neutral", "happy", "waving", "bored", "surprised", "sad", "proud")
SLOTS = (2, 4, 1, 5)  # screens for sessions, nearest the companion first; screen 3 is the companion
STALE_AFTER = 3 * 60 * 60  # a session silent this long is gone (closed app, killed process)
REACTION_SECONDS = 20
LONG_TASK = 30 * 60


class StateError(ValueError):
    pass


def today() -> str:
    return date.today().isoformat()


def empty() -> dict:
    return {
        "day": today(),
        "sessions": {},
        "done_today": 0,
        "done_total": 0,  # all-time finished turns: the robot's experience points
        "busy_hours": {},  # local hour -> seconds Claude spent thinking/working today
        "companion": {"emotion": "neutral", "until": 0},
        "overlays": {},
        "last_event": 0,
        "account": None,  # email of the Claude account behind the latest event
    }


def load() -> dict:
    try:
        # Defaults first, so a state file from an older version still has every key.
        return {**empty(), **json.loads(PATH.read_text())}
    except FileNotFoundError:
        return empty()


def rollover(s: dict):
    if s["day"] != today():
        s["day"], s["done_today"], s["busy_hours"] = today(), 0, {}
    for sid, sess in list(s["sessions"].items()):
        if time.time() - sess["at"] > STALE_AFTER:
            del s["sessions"][sid]


@contextmanager
def mutate():
    DATA.mkdir(exist_ok=True)
    with open(DATA / "state.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        s = load()
        rollover(s)
        yield s
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1))
        os.replace(tmp, PATH)


HEALTH = DATA / "daemon.json"
HEALTH_STALE = 15


def write_health(error):
    """Daemon heartbeat, so the MCP server can tell Claude when the screens are not updating."""
    DATA.mkdir(exist_ok=True)
    tmp = HEALTH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"at": time.time(), "error": error}, ensure_ascii=False))
    os.replace(tmp, HEALTH)


def health_warning():
    try:
        h = json.loads(HEALTH.read_text())
    except (OSError, ValueError):
        h = {"at": 0, "error": None}
    if time.time() - h["at"] > HEALTH_STALE:
        return "Демон ворот не запущен: состояние сохранено, но экраны не обновятся, пока он не стартует."
    if h["error"]:
        return f"Ворота сейчас недоступны, демон повторит попытку: {h['error']}"
    return None


def live_sessions(s: dict) -> dict:
    """Sessions of the active Claude account by screen number, ignoring ones gone stale since the last write.

    The active account is the one behind the latest event: switch accounts in the Claude app, start working,
    and the gate follows. Sessions with no known account (terminal, old state) show for everyone."""
    me = s.get("account")
    return {sess["slot"]: sess for sess in s["sessions"].values()
            if sess["slot"] and time.time() - sess["at"] <= STALE_AFTER and sess.get("account") in (None, me)}


BUSY = ("thinking", "working")


def _count_busy(s: dict, sess: dict):
    """Leaving a busy status: spread the time it lasted over the local hours it covered."""
    if sess["status"] not in BUSY:
        return
    t, end = sess["since"], time.time()
    while t < end:
        hour = datetime.fromtimestamp(t).replace(minute=0, second=0, microsecond=0)
        nxt = min(end, (hour + timedelta(hours=1)).timestamp())
        if hour.date() == date.today():
            key = str(hour.hour)
            s["busy_hours"][key] = s["busy_hours"].get(key, 0) + nxt - t
        t = nxt


def _react(s: dict, emotion: str):
    s["companion"] = {"emotion": emotion, "until": time.time() + REACTION_SECONDS}
    s["last_event"] = time.time()


def _clean(text: str, limit: int = 200) -> str:
    text = " ".join(str(text).split())
    if not text:
        raise StateError("Пустой текст")
    return text[:limit]


# --- operations: used by the hook, the MCP tools and the CLI; each returns something printable ---

def update_session(sid: str, name: str, status: str, text: str = "", account: str = None) -> dict:
    if status not in STATUSES:
        raise StateError(f"Статус должен быть одним из: {', '.join(STATUSES)}")
    with mutate() as s:
        sess = s["sessions"].setdefault(sid, {"name": _clean(name, 40), "status": None, "since": 0, "slot": None,
                                              "account": account or None})
        if account:
            s["account"] = account
        if sess["slot"] is None:
            # Screens are shared between accounts: only the other sessions of this account hold one.
            # A session with no known account shows for everyone, so it holds its screen in every account.
            mine = sess.get("account")
            taken = {x["slot"] for x in s["sessions"].values() if None in (mine, x.get("account"))
                     or x.get("account") == mine}
            free = [n for n in SLOTS if n not in taken]
            # shortcut: a fifth session gets no screen until one frees up; add paging if that gets common
            sess["slot"] = free[0] if free else None
        if sess["status"] != status:
            _count_busy(s, sess)
            long_job = sess["status"] in BUSY and time.time() - sess["since"] > LONG_TASK
            sess["since"] = time.time()
            if status == "done":
                s["done_today"] += 1
                s["done_total"] += 1
                if long_job:
                    _react(s, "proud")  # a long job finally done is worth a celebration
                else:
                    s["companion"]["until"] = 0  # straight to pointing at it: one redraw, not two
            elif status == "error":
                _react(s, "surprised")
        sess.update(status=status, at=time.time(), text=" ".join(str(text).split())[:120])
        s["last_event"] = time.time()
        return sess


def end_session(sid: str) -> dict:
    with mutate() as s:
        sess = s["sessions"].pop(sid, {})
        if sess:
            _count_busy(s, sess)
        return sess


def set_agent_status(status: str, text: str = "") -> dict:
    """The Claude app chat has no hooks, so it reports itself through the MCP tool."""
    return update_session("chat", "чат", status, text)


def companion_react(emotion: str) -> dict:
    if emotion not in EMOTIONS:
        raise StateError(f"Эмоция должна быть одной из: {', '.join(EMOTIONS)}")
    with mutate() as s:
        _react(s, emotion)
        return s["companion"]


def show_text(screen: int, text: str, duration: int = 60) -> dict:
    if int(screen) not in range(1, 6):
        raise StateError("Экран: от 1 до 5")
    with mutate() as s:
        s["overlays"][str(int(screen))] = {"text": _clean(text), "until": time.time() + max(1, int(duration))}
        return s["overlays"][str(int(screen))]


def busy_hours(s: dict) -> dict:
    """Today's busy seconds per hour, including sessions still thinking or working right now."""
    view = {"busy_hours": dict(s["busy_hours"])}
    for sess in s["sessions"].values():
        _count_busy(view, sess)
    return view["busy_hours"]


def level(xp: int):
    """(level, xp into this level, xp this level needs): each level asks 10 more turns than the last."""
    n, need = 1, 10
    while xp >= need:
        xp, n, need = xp - need, n + 1, need + 10
    return n, xp, need
