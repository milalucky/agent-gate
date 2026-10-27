#!/bin/bash
# Registers the times-gate MCP server in the Claude app.
# The app rewrites its config from memory when it quits, so this waits for it to close,
# patches the file and opens the app again. Run it, then quit Claude with Cmd+Q.
# Real path: macOS blocks apps from ~/Desktop, so the config must not go through the Desktop link.
DIR="$(cd "$(dirname "$0")" && pwd -P)"
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# lsappinfo, not pgrep: sandboxed shells cannot see the app's process.
while [ -n "$(lsappinfo find name=Claude)" ]; do sleep 1; done
sleep 2
/usr/bin/python3 - "$CONFIG" "$DIR/mcp_server.py" <<'EOF'
import json, sys
path, server = sys.argv[1], sys.argv[2]
cfg = json.load(open(path))
cfg.setdefault("mcpServers", {})["times-gate"] = {"command": "/usr/bin/python3", "args": [server]}
json.dump(cfg, open(path, "w"), indent=2, ensure_ascii=False)
EOF
open -a Claude
