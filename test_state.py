"""Self-check of sessions, accounts, limits, the hook and the companion: python3 test_state.py"""
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import hook
import render
import robot
import state

os.environ.pop("CLAUDE_CODE_USER_EMAIL", None)  # hermetic: no account from the session running the test
state.DATA = Path(tempfile.mkdtemp())
state.PATH = state.DATA / "state.json"
import limits
limits.PATH = state.DATA / "limits.json"


def fire(event: dict):
    sys.stdin = io.StringIO(json.dumps({"session_id": "a", "cwd": "/Users/x/TimesGate", **event}))
    hook.main()


# The hook maps Claude Code events onto session statuses on the first free screen.
fire({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})
s = state.load()
assert s["sessions"]["a"]["slot"] == 2 and s["sessions"]["a"]["status"] == "thinking", "nearest the companion first"
assert s["sessions"]["a"]["name"] == "TimesGate"
fire({"hook_event_name": "PreToolUse", "tool_name": "Bash"})
fire({"hook_event_name": "Notification", "notification_type": "idle_prompt", "message": "Claude is waiting for your input"})
assert state.load()["sessions"]["a"]["status"] == "working", "the idle nudge changes nothing"
fire({"hook_event_name": "Notification", "message": "Claude needs your permission to use Bash"})
assert state.load()["sessions"]["a"]["status"] == "waiting_for_user"
assert render.companion_emotion(state.load()) == ("waving", -1), "points left at screen 2"
fire({"hook_event_name": "Stop"})
s = state.load()
assert s["sessions"]["a"]["status"] == "done" and s["done_today"] == 1
assert render.companion_emotion(s) == ("waving", -1), "a finished turn: straight to pointing at it"

# A long job finished: the companion celebrates instead of just pointing.
state.update_session("long", "long", "working")
with state.mutate() as s:
    s["sessions"]["long"]["since"] -= state.LONG_TASK + 1
state.update_session("long", "long", "done")
assert state.load()["companion"]["emotion"] == "proud"
state.end_session("long")

# Slots: screens 2, 4, 1, 5 in that order; a freed screen goes to the next new session; a fifth session waits.
for sid in "bcd":
    state.update_session(sid, sid, "working")
assert {x["slot"] for x in state.load()["sessions"].values()} == {1, 2, 4, 5}
state.update_session("e", "e", "waiting_for_user")
assert state.load()["sessions"]["e"]["slot"] is None
fire({"hook_event_name": "SessionEnd", "reason": "exit"})
state.update_session("e", "e", "waiting_for_user")
s = state.load()
assert s["sessions"]["e"]["slot"] == 2 and "a" not in s["sessions"]

# Companion: points right at a waiting session on screen 4 or 5.
s["companion"]["until"] = 0
for x in s["sessions"].values():
    x["status"] = "working"
s["sessions"]["d"]["status"] = "waiting_for_user"
assert render.companion_emotion(s) == ("waving", 1)
s["sessions"]["d"]["status"] = "working"
assert render.companion_emotion(s) == ("scanning", 0), "working sessions on both sides: it scans"
for x in s["sessions"].values():
    x["status"] = "working" if x["slot"] in (4, 5) else "idle"
assert render.companion_emotion(s) == ("watching", 1), "only the right side works: it watches right"
done = dict(s, sessions={k: dict(x, status="done", since=time.time() - render.POINT_AT_DONE_FOR - 1)
                         for k, x in s["sessions"].items()})
assert render.companion_emotion(done)[0] == "neutral", "a long-finished session is not pointed at forever"
done["last_event"] = time.time() - render.BORED_AFTER - 1
assert render.companion_emotion(done)[0] == "bored"
assert len(render.companion_screen(s)) > 1

# Stale sessions disappear; the chat reports through the MCP tool.
s["sessions"]["b"]["at"] = time.time() - state.STALE_AFTER - 1
state.PATH.write_text(json.dumps(s))
state.set_agent_status("thinking")
s = state.load()
assert "b" not in s["sessions"] and s["sessions"]["chat"]["slot"] == 4

assert render.duration(59) == "<5м" and render.duration(1799) == "25м" and render.duration(5400) == "1ч30"
assert render.duration(3725) == "1ч" and render.duration(90000) == "1д1ч"

# Limits come from the text of /usage.
from datetime import datetime
usage = """You are currently using your subscription to power your Claude Code usage

Current session: 29% used · resets Oct 27 at 3:50pm (Asia/Yekaterinburg)
Current week (all models): 51% used · resets Oct 30 at 1am (Asia/Yekaterinburg)
Current week (Fable): 72% used · resets Oct 30 at 1am (Asia/Yekaterinburg)"""
got = limits.parse(usage, datetime(2026, 10, 27, 11, 0))
assert got["five_hour"] == {"used_percentage": 29.0, "resets_at": datetime(2026, 10, 27, 15, 50).timestamp()}
assert got["seven_day"] == {"used_percentage": 51.0, "resets_at": datetime(2026, 10, 30, 1, 0).timestamp()}
assert limits.parse("Current week (all models): 3% used · resets Jan 2 at 9am", datetime(2026, 12, 30))[
    "seven_day"]["resets_at"] == datetime(2027, 1, 2, 9).timestamp(), "a reset in January is next year"
assert limits.parse("nothing here") == {}


now = time.time()
pace = {"five_hour": {"used_percentage": 60, "resets_at": now + 3 * 3600}, "history": [[now - 3600, 20], [now, 60]]}
assert abs(limits.forecast(pace) - 3600) < 5, "40%/h with 40% left: one hour"
pace["five_hour"]["resets_at"] = now + 1800
assert limits.forecast(pace) is None, "resets before it would run out"
assert limits.forecast({"history": [[now - 60, 1], [now, 2]]}) is None, "too short a span to judge"
assert set(robot.STATUSES) == set(state.STATUSES) and set(robot.EMOTIONS) == set(state.EMOTIONS)
screens = render.render_all(state.load())
assert len(screens) == 5 and all(len(f) > 1 for f in screens), "every screen in use animates"

# Busy time: a finished thinking/working spell lands in today's hours; turns feed the level.
assert sum(state.busy_hours(state.load()).values()) > 0
assert state.load()["done_total"] == 2  # session a and the long job

# No sessions: four different widgets around the companion, nothing empty or repeated.
for sid in list(state.load()["sessions"]):
    state.end_session(sid)
screens = render.render_all(state.load())
firsts = [f[0].tobytes() for f in screens]
assert len(set(firsts)) == 5, "every screen differs"
assert render.plural(1, "a", "b", "c") == "a" and render.plural(3, "a", "b", "c") == "b"
assert render.plural(12, "a", "b", "c") == "c" and render.plural(21, "a", "b", "c") == "a"
# Account switch: the gate follows the account behind the latest event (the app puts it in the hook's env).
os.environ["CLAUDE_CODE_USER_EMAIL"] = "work@example.com"
sys.stdin = io.StringIO(json.dumps({"session_id": "w1", "cwd": "/x/work-proj", "hook_event_name": "UserPromptSubmit"}))
hook.main()
state.update_session("h1", "home-proj", "working", account="home@example.com")
s = state.load()
names = {x["name"] for x in state.live_sessions(s).values()}
assert s["account"] == "home@example.com" and "home-proj" in names and "work-proj" not in names
assert s["sessions"]["h1"]["slot"] == 2, "the other account's sessions don't take this account's screens"
hook.main.__globals__["sys"].stdin = io.StringIO(json.dumps(
    {"session_id": "w1", "cwd": "/x/work-proj", "hook_event_name": "PreToolUse", "tool_name": "Read"}))
hook.main()
assert "work-proj" in {x["name"] for x in state.live_sessions(state.load()).values()}

# Limits are kept per account; the gate shows the active account's.
limits.PATH.write_text(json.dumps({"at": 1, "accounts": {
    "work@example.com": {"label": "работа", "five_hour": {"used_percentage": 5}},
    "home@example.com": {"label": "личный", "five_hour": {"used_percentage": 29}}}}))
assert limits.for_account("home@example.com")["five_hour"]["used_percentage"] == 29
assert limits.for_account("nobody@example.com") is None and limits.for_account(None) is None
state.end_session("w1"); state.end_session("h1")
print("ok")
