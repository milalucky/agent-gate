"""MCP server (stdio) for the Claude app: tools change the dashboard state, the daemon redraws.

Hand-rolled JSON-RPC because the official `mcp` SDK needs Python 3.10+ and this Mac has 3.9.
The server never talks to the device, so a dead Times Gate cannot break it.
"""
import json
import sys
import time

import render
import state

S = {"type": "string"}
I = {"type": "integer"}


def tool(name, description, props=None, required=()):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}, "required": list(required)}}


TOOLS = [
    tool("set_agent_status", "Статус этого чата в приложении Claude на воротах Times Gate (у сессий Claude Code "
         "статус ставится сам). Ставь thinking/working в начале ответа, done или waiting_for_user в конце.",
         {"status": {"type": "string", "enum": list(state.STATUSES)},
          "text": {**S, "description": "Коротко, над чем работаешь"}}, ["status"]),
    tool("companion_react", "Ручная реакция робота-компаньона на центральном экране.",
         {"emotion": {"type": "string", "enum": list(state.EMOTIONS)}}, ["emotion"]),
    tool("show_text", "Временно показать короткий текст крупно на экране 1-5 (до ~40 символов).",
         {"screen": {**I, "minimum": 1, "maximum": 5}, "text": S,
          "duration": {**I, "description": "Секунды, по умолчанию 60"}}, ["screen", "text"]),
    tool("get_dashboard_state", "Какие сессии Claude на каких экранах и в каком они статусе."),
]


def dashboard_state():
    s = state.load()
    state.rollover(s)
    return {"screens": {n: {k: x[k] for k in ("name", "status", "text")} for n, x in state.live_sessions(s).items()},
            "done_today": s["done_today"], "companion": render.companion_emotion(s)[0],
            "overlays": {k: v for k, v in s["overlays"].items() if v["until"] > time.time()}}


CALLS = {
    "set_agent_status": lambda a: state.set_agent_status(a["status"], a.get("text", "")),
    "companion_react": lambda a: state.companion_react(a["emotion"]),
    "show_text": lambda a: state.show_text(a["screen"], a["text"], a.get("duration", 60)),
    "get_dashboard_state": lambda a: dashboard_state(),
}


def call(name, args):
    try:
        out = json.dumps(CALLS[name](args or {}), ensure_ascii=False)
    except KeyError as exc:
        return f"Не хватает параметра или нет такого инструмента: {exc}", True
    except (state.StateError, ValueError, TypeError) as exc:
        return f"Ошибка: {exc}", True
    warning = state.health_warning()
    return (f"{out}\n\n⚠ {warning}" if warning else out), False


def handle(msg):
    method, params = msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "times-gate", "version": "0.1"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        text, is_error = call(params.get("name"), params.get("arguments"))
        return {"content": [{"type": "text", "text": text}], "isError": is_error}
    if method == "ping":
        return {}
    raise LookupError(method)


def main():
    # The Claude app may start us without a UTF-8 locale; Cyrillic must survive either way.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if "id" not in msg:
            continue  # notifications need no reply
        reply = {"jsonrpc": "2.0", "id": msg["id"]}
        try:
            reply["result"] = handle(msg)
        except LookupError:
            reply["error"] = {"code": -32601, "message": f"Method not found: {msg.get('method')}"}
        except Exception as exc:  # never die on one bad request
            reply["error"] = {"code": -32603, "message": str(exc)}
        sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
