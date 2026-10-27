"""Manual control of the dashboard state; the running daemon picks changes up within a second.

  python3 cli.py session demo1 TimesGate working   # fake a Claude Code session on a free screen
  python3 cli.py end demo1
  python3 cli.py status done                       # the Claude app chat's status
  python3 cli.py react happy | show 4 "текст" [-d 30] | state
  python3 cli.py preview                           # write preview.png of all five screens, no device needed
"""
import argparse
import json
import sys

from PIL import Image

import render
import state


def main():
    p = argparse.ArgumentParser(description="Times Gate dashboard")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("session"); a.add_argument("id"); a.add_argument("name"); a.add_argument("status", choices=state.STATUSES)
    sub.add_parser("end").add_argument("id")
    a = sub.add_parser("status"); a.add_argument("status", choices=state.STATUSES); a.add_argument("text", nargs="?", default="")
    sub.add_parser("react").add_argument("emotion", choices=state.EMOTIONS)
    a = sub.add_parser("show"); a.add_argument("screen", type=int); a.add_argument("text"); a.add_argument("-d", "--duration", type=int, default=60)
    sub.add_parser("state")
    sub.add_parser("preview")
    args = p.parse_args()

    try:
        if args.cmd == "session":
            out = state.update_session(args.id, args.name, args.status)
        elif args.cmd == "end":
            out = state.end_session(args.id)
        elif args.cmd == "status":
            out = state.set_agent_status(args.status, args.text)
        elif args.cmd == "react":
            out = state.companion_react(args.emotion)
        elif args.cmd == "show":
            out = state.show_text(args.screen, args.text, args.duration)
        elif args.cmd == "state":
            out = state.load()
        else:
            sheet = Image.new("RGB", (5 * 132 - 4, 128), (0, 0, 0))
            for i, frames in enumerate(render.render_all(state.load())):
                sheet.paste(frames[0], (i * 132, 0))
            out = str(state.DATA.parent / "preview.png")
            sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(out)
    except state.StateError as exc:
        sys.exit(f"Ошибка: {exc}")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
