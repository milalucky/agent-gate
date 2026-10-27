"""Claude Code hook: reports each session's status to the dashboard, with no help from the model.

Registered in ~/.claude/settings.json for SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
PermissionRequest, Notification, Stop, StopFailure and SessionEnd. Reads the hook JSON on stdin and always exits 0,
so a broken dashboard can never get in Claude's way.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STATUS = {
    "SessionStart": "idle",
    "UserPromptSubmit": "thinking",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "PermissionRequest": "waiting_for_user",  # prints nothing, so it never answers the prompt itself
    "Stop": "done",
    "StopFailure": "error",
}


def name_for(cwd: str) -> str:
    # Sessions without a project folder live in the app's scratch workspaces.
    return "сессия" if "scratch-workspaces" in cwd else (Path(cwd).name or "сессия")


def status_for(event: dict):
    kind = event.get("hook_event_name")
    if kind == "Notification":
        # Only a permission prompt blocks the session; the 60 s "waiting for input" nudge changes nothing.
        text = f"{event.get('notification_type', '')} {event.get('message', '')}".lower()
        return "waiting_for_user" if "permission" in text else None
    return STATUS.get(kind)


def main():
    import state
    event = json.load(sys.stdin)
    sid = event["session_id"]
    if event.get("hook_event_name") == "SessionEnd":
        state.end_session(sid)
        return
    status = status_for(event)
    if status:
        # The Claude app tells every session which account it runs under; a terminal session may not.
        state.update_session(sid, name_for(event.get("cwd", "")), status, event.get("tool_name", ""),
                             os.environ.get("CLAUDE_CODE_USER_EMAIL"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
