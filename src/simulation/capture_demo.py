"""
capture_demo.py — capture exactly the MetaWorld Demo (or any named cv2) window.

Usage:
    python3 capture_demo.py                        # one shot → /tmp/demo_capture.png
    python3 capture_demo.py --out my.png
    python3 capture_demo.py --window "OCI Robot Cloud"
    python3 capture_demo.py --watch               # live: re-capture every 3s
"""

import argparse
import subprocess
import sys
import time

try:
    import Quartz
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "pyobjc-framework-Quartz", "-q"])
    import Quartz


def find_window(title_fragment: str) -> dict | None:
    """Return CGWindow info dict for the first window whose name contains title_fragment."""
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
    )
    for w in wins:
        name = w.get("kCGWindowName") or ""
        if title_fragment.lower() in name.lower():
            return w
    return None


def capture_window(title_fragment: str, out_path: str) -> dict | None:
    """Capture the window by title fragment using screencapture -l <wid>. Returns window info or None."""
    w = find_window(title_fragment)
    if w is None:
        print(f"[capture_demo] Window '{title_fragment}' not found on screen.")
        return None

    wid   = w["kCGWindowNumber"]
    b     = w["kCGWindowBounds"]
    name  = w.get("kCGWindowName", "")
    owner = w.get("kCGWindowOwnerName", "")

    # screencapture -l captures exactly that window (including shadow)
    subprocess.run(["screencapture", "-x", "-l", str(wid), out_path], check=True)
    print(f"[capture_demo] Captured '{name}' (owner={owner}, WID={wid}) "
          f"pos=({b['X']:.0f},{b['Y']:.0f}) size={b['Width']:.0f}x{b['Height']:.0f} → {out_path}")
    return w


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--window", default="MetaWorld Demo", help="Window title fragment to search for")
    p.add_argument("--out",    default="/tmp/demo_capture.png", help="Output PNG path")
    p.add_argument("--watch",  action="store_true", help="Re-capture every --interval seconds")
    p.add_argument("--interval", type=float, default=3.0, help="Watch interval in seconds")
    args = p.parse_args()

    if args.watch:
        print(f"Watching for '{args.window}' every {args.interval}s — Ctrl+C to stop")
        i = 0
        while True:
            out = args.out.replace(".png", f"_{i:04d}.png")
            capture_window(args.window, out)
            time.sleep(args.interval)
            i += 1
    else:
        w = capture_window(args.window, args.out)
        if w is None:
            sys.exit(1)


if __name__ == "__main__":
    main()
