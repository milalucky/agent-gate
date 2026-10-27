#!/bin/bash
# Sets up Agent Gate on this Mac: checks Python + Pillow, registers the Claude Code hooks
# and starts the daemon at login with launchd. Safe to run again.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd -P)"
PY=/usr/bin/python3
LABEL=com.agentgate.daemon
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "$DIR" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    echo "macOS blocks background apps from $DIR. Move the folder (e.g. to ~/agent-gate) and run again."; exit 1;;
esac

"$PY" -c "import PIL" 2>/dev/null || "$PY" -m pip install --user pillow
if [ ! -f "$DIR/.env" ]; then
  cp "$DIR/.env.example" "$DIR/.env"
  echo "Created .env: fill in DIVOOM_IP and DIVOOM_TOKEN, then run ./install.sh again."; exit 0
fi

# Claude Code hooks: every session reports its status to the gate.
"$PY" - "$DIR/hook.py" <<'PY'
import json, os, sys
path = os.path.expanduser("~/.claude/settings.json")
cfg = json.load(open(path)) if os.path.exists(path) else {}
cmd = f"/usr/bin/python3 {sys.argv[1]}"
for ev in ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
           "Notification", "Stop", "StopFailure", "SessionEnd"]:
    groups = cfg.setdefault("hooks", {}).setdefault(ev, [])
    if not any(h.get("command") == cmd for g in groups for h in g.get("hooks", [])):
        groups.append({"hooks": [{"type": "command", "command": cmd, "timeout": 5}]})
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(cfg, open(path, "w"), indent=2, ensure_ascii=False)
print("Hooks registered in", path)
PY

mkdir -p "$DIR/data" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/daemon.py</string></array>
    <key>WorkingDirectory</key><string>$DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$DIR/data/launchd.log</string>
    <key>StandardErrorPath</key><string>$DIR/data/launchd.log</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Daemon started. Log: $DIR/data/daemon.log"
