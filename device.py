"""Times Gate transport: the device pulls each screen as a GIF from a small HTTP server on this Mac.

Pushing JPEGs with Draw/SendHttpGif is known to knock the device off Wi-Fi, so we only send
the tiny Device/PlayGif command and let the device fetch the picture itself.
"""
import base64
import hashlib
import io
import json
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

FRAME_PORT = 8477
FETCH_TIMEOUT = 10
SHIFT = bytes(min(i + 1, 255) for i in range(256))


class DeviceError(Exception):
    pass


def env() -> dict:
    out = {}
    for line in (Path(__file__).parent / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def gif(frames: list) -> bytes:
    # One palette for all frames, quantized from the frames stacked into one sheet.
    sheet = Image.new("RGB", (128, 128 * len(frames)))
    for row, frame in enumerate(frames):
        sheet.paste(frame.convert("RGB"), (0, row * 128))
    q = sheet.quantize(colors=255)
    # Firmware draws palette entry 0 as transparent, so shift every pixel up one entry.
    shifted = Image.frombytes("P", q.size, q.tobytes().translate(SHIFT))
    shifted.putpalette([0, 0, 0] + q.getpalette()[: 255 * 3])
    images = [shifted.crop((0, row * 128, 128, (row + 1) * 128)) for row in range(len(frames))]
    buf = io.BytesIO()
    if len(images) > 1:
        # optimize=False keeps the palette order, and with it the unused entry 0.
        images[0].save(buf, "GIF", save_all=True, append_images=images[1:], loop=0, optimize=False,
                       duration=[f.info.get("duration", 200) for f in frames])
    else:
        images[0].save(buf, "GIF", optimize=False)
    return buf.getvalue()


class Device:
    def __init__(self):
        e = env()
        self.ip = e.get("DIVOOM_IP", "")  # may be empty: then the daemon finds the gate by DIVOOM_MAC
        self.token = int(e["DIVOOM_TOKEN"])
        self.mac = e.get("DIVOOM_MAC", "").lower()
        # "push" sends JPEG frames straight to the gate: a shorter loading hourglass, but pushing has been
        # reported to knock the gate off Wi-Fi after a few hundred uploads. "pull" (default) is the safe path.
        self.push = e.get("DIVOOM_TRANSPORT", "pull") == "push"
        self.pic_id = 0
        self.files = {}
        self.fetched = {}

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = outer.files.get(self.path)
                if self.client_address[0] != outer.ip or data is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                outer.fetched[self.path].set()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("0.0.0.0", FRAME_PORT), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def command(self, payload: dict) -> dict:
        body = json.dumps({**payload, "LocalToken": self.token}).encode()
        try:
            reply = json.loads(urllib.request.urlopen(f"http://{self.ip}/post", body, timeout=10).read() or b"{}")
        except (OSError, ValueError) as exc:
            raise DeviceError(f"Times Gate не отвечает ({self.ip}): {exc}") from exc
        if reply.get("error_code", 0) != 0:
            raise DeviceError(f"Times Gate отклонил команду: {reply}")
        return reply

    def rediscover(self) -> bool:
        """The router may hand the gate a new address; find it again by its MAC. True if it moved."""
        if not self.mac:
            return False
        subnet = self.local_ip().rsplit(".", 1)[0]
        # Ping the whole /24 at once so the ARP table learns every live host, then look the MAC up.
        pings = [subprocess.Popen(["ping", "-c1", "-W", "300", f"{subnet}.{i}"], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL) for i in range(1, 255)]
        for proc in pings:
            proc.wait()
        arp = subprocess.run(["arp", "-an"], capture_output=True, text=True).stdout
        found = next((line.split("(")[1].split(")")[0] for line in arp.splitlines()
                      if f" at {self.mac} " in line.lower() + " "), None)
        if found and found != self.ip:
            self.ip = found
            return True
        return False

    def push_frames(self, screen: int, frames: list):
        # IDs must only grow, even within one second.
        self.pic_id = max(int(time.time()), self.pic_id + 1)
        mask = [int(i == screen) for i in range(5)]
        for offset, frame in enumerate(frames):
            buf = io.BytesIO()
            frame.convert("RGB").save(buf, "JPEG", quality=90)
            self.command({"Command": "Draw/SendHttpGif", "LcdArray": mask, "PicNum": len(frames), "PicOffset": offset,
                          "PicID": self.pic_id, "PicSpeed": frames[0].info.get("duration", 200), "PicWidth": 128,
                          "PicData": base64.b64encode(buf.getvalue()).decode("ascii")})
            time.sleep(0.1)  # the pacing the firmware is known to cope with

    def local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self.ip, 80))
                return s.getsockname()[0]
        except OSError as exc:  # Wi-Fi off or just waking from sleep
            raise DeviceError(f"Нет сети до {self.ip}: {exc}") from exc

    def show(self, screen: int, frames: list):
        """Show frames (a still or a looping animation) on screen 0-4; wait until the device fetched them."""
        if self.push:
            return self.push_frames(screen, frames)
        data = gif(frames)
        path = f"/{screen}-{hashlib.sha1(data).hexdigest()[:12]}.gif"
        # Keep only the latest picture per screen; a stale URL then 404s instead of piling up.
        self.files = {k: v for k, v in self.files.items() if not k.startswith(f"/{screen}-")}
        self.fetched = {k: v for k, v in self.fetched.items() if k in self.files}
        self.fetched[path] = threading.Event()
        self.files[path] = data
        mask = [int(i == screen) for i in range(5)]
        self.command({"Command": "Device/PlayGif", "LcdArray": mask,
                      "FileName": [f"http://{self.local_ip()}:{FRAME_PORT}{path}"]})
        if not self.fetched[path].wait(FETCH_TIMEOUT):
            raise DeviceError(f"Экран {screen + 1}: устройство не скачало картинку за {FETCH_TIMEOUT} с")
