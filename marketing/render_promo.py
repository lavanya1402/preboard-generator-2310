"""Record marketing/promo.html as an MP4 (1080x1350, 30 fps) using headless Edge + ffmpeg.

Every CSS animation is paused and set to the exact frame time, so the video is smooth and
identical on every run.

Needs: Microsoft Edge, `websockets` (already in .venv), and ffmpeg from the `imageio-ffmpeg`
package (pip install imageio-ffmpeg, or pass --ffmpeg PATH).
Run:
    .venv\\Scripts\\python.exe marketing\\render_promo.py [--seconds 30] [--fps 30] [--preview 3,10,16,23,28]
"""
import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

HERE = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H, PORT = 1080, 1350, 9339


async def capture(times, out_dir):
    profile = tempfile.mkdtemp(prefix="promo_edge_")
    edge = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={profile}", f"--window-size={W},{H}", (HERE / "promo.html").as_uri()],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            msg_id = 0

            async def send(method, **params):
                nonlocal msg_id
                msg_id += 1
                await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
                while True:
                    reply = json.loads(await ws.recv())
                    if reply.get("id") == msg_id:
                        return reply.get("result", {})

            await send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
            await send("Runtime.evaluate", expression="document.fonts.ready.then(() => 1)", awaitPromise=True)
            await asyncio.sleep(1.0)  # let images decode
            for i, t in enumerate(times):
                await send("Runtime.evaluate", expression=(
                    "document.getAnimations().forEach(a => { a.pause(); a.currentTime = %d; })" % round(t * 1000)))
                shot = await send("Page.captureScreenshot", format="png",
                                  clip={"x": 0, "y": 0, "width": W, "height": H, "scale": 1})
                (out_dir / f"f{i:04d}.png").write_bytes(base64.b64decode(shot["data"]))
                if i % 30 == 0:
                    print(f"{t:.0f}s", end=" ", flush=True)
    finally:
        edge.terminate()
        edge.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--out", default=str(HERE / "preboard-generator-promo.mp4"))
    ap.add_argument("--preview", help="comma-separated seconds: save only these frames as PNG for checking")
    ap.add_argument("--ffmpeg")
    args = ap.parse_args()

    if args.preview:
        out_dir = HERE / "preview"
        out_dir.mkdir(exist_ok=True)
        asyncio.run(capture([float(t) for t in args.preview.split(",")], out_dir))
        print(f"Preview frames in {out_dir}")
        return

    frames = Path(tempfile.mkdtemp(prefix="promo_frames_"))
    times = [i / args.fps for i in range(int(args.seconds * args.fps))]
    asyncio.run(capture(times, frames))
    ffmpeg = args.ffmpeg
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", str(frames / "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", args.out], check=True)
    shutil.rmtree(frames, ignore_errors=True)
    print(f"Saved {args.out} ({Path(args.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
