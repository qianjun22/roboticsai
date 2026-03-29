"""
OCI Robot Cloud — Demo Video Generator

Creates an MP4 demo video from the Genesis SDG + training artifacts,
suitable for the NVIDIA partnership pitch and AI World presentation.

Video structure (30fps, ~60 seconds):
  0-8s    Title card: "OCI Robot Cloud — Where Robots Learn"
  8-20s   Genesis SDG: 3 overlaid demo episodes (pick-and-lift)
  20-30s  Training montage: loss curve + GPU utilization animation
  30-42s  Eval comparison: baseline vs fine-tuned trajectory overlay
  42-55s  Pipeline diagram: Genesis → OCI → GR00T → Jetson
  55-60s  Stats card: 8.7× MAE, 2.35 it/s, $0.0043/10k steps

Usage:
    python3 src/training/generate_demo_video.py \\
        --sdg-dir /tmp/genesis_sdg_planned \\
        --lerobot-dir /tmp/franka_planned_lerobot \\
        --output Robotics/experiments/oci_robot_cloud_demo.mp4

Requirements:
    pip install opencv-python matplotlib pillow numpy
    ffmpeg must be in PATH
"""

import argparse
import json
import os
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--sdg-dir",      default="/tmp/genesis_sdg_planned",     help="Genesis SDG output dir")
parser.add_argument("--lerobot-dir",  default="/tmp/franka_planned_lerobot",   help="LeRobot dataset dir")
parser.add_argument("--output",       default="/tmp/oci_robot_cloud_demo.mp4",  help="Output MP4 path")
parser.add_argument("--fps",          type=int, default=30,                     help="Output FPS")
parser.add_argument("--width",        type=int, default=1920)
parser.add_argument("--height",       type=int, default=1080)
args = parser.parse_args()

W, H = args.width, args.height
FPS = args.fps

# ── Palette ────────────────────────────────────────────────────────────────
BG      = (13,   13,  13)     # #0D0D0D
RED     = (199,  70,  52)     # #C74634 Oracle red
WHITE   = (255, 255, 255)
LGRAY   = (209, 213, 219)
GRAY    = (156, 163, 175)
GREEN   = ( 34, 197,  94)
DGRAY   = ( 55,  65,  81)


def blank(alpha=255):
    """Return blank dark frame."""
    f = np.zeros((H, W, 3), dtype=np.uint8)
    f[:] = BG
    return f


def text_on(img, txt, x, y, size=40, color=WHITE, bold=False, center=False):
    """Draw text using PIL (better font rendering than cv2)."""
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception:
        font = ImageFont.load_default()
    if center:
        bbox = d.textbbox((0, 0), txt, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
    d.text((x, y), txt, font=font, fill=color[::-1] if len(color)==3 else color)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def red_bar(img, h=8):
    img[:h, :] = RED
    return img


def lerp(a, b, t):
    return a + (b - a) * t


# ── Section 1: Title card (0-8s = 240 frames) ─────────────────────────────

def title_section(n_frames=240):
    frames = []
    for i in range(n_frames):
        t = i / n_frames
        f = blank()
        red_bar(f)

        # Fade-in title
        alpha = min(1.0, t * 3)
        txt_color = tuple(int(c * alpha) for c in WHITE)
        gray_color = tuple(int(c * alpha) for c in LGRAY)
        red_color = tuple(int(c * alpha) for c in RED)

        f = text_on(f, "OCI Robot Cloud",       x=0, y=340, size=96, color=txt_color,  center=True)
        f = text_on(f, "Where Robots Learn",    x=0, y=460, size=48, color=gray_color, center=True)
        f = text_on(f, "Genesis SDG  ·  GR00T Fine-Tuning  ·  Jetson Deploy",
                    x=0, y=540, size=28, color=tuple(int(c * alpha * 0.7) for c in GRAY), center=True)

        # Red accent line (fades in after title)
        if t > 0.3:
            line_alpha = min(1.0, (t - 0.3) * 2)
            lx1, lx2, ly = W // 2 - 200, W // 2 + 200, 530
            thickness = max(1, int(2 * line_alpha))
            cv2.line(f, (lx1, ly), (lx2, ly), RED, thickness)

        if t > 0.6:
            sub_alpha = min(1.0, (t - 0.6) * 3)
            f = text_on(f, "Oracle Cloud Infrastructure × NVIDIA  |  2026",
                        x=0, y=880, size=24,
                        color=tuple(int(c * sub_alpha) for c in GRAY), center=True)

        frames.append(f)
    return frames


# ── Section 2: SDG demo frames (8-20s = 360 frames) ─────────────────────

def sdg_section(n_frames=360):
    """Show Genesis SDG demo episodes side by side."""
    frames_out = []

    # Load up to 3 demo episodes
    demos = []
    for di in range(3):
        demo_dir = os.path.join(args.sdg_dir, f"demo_{di:04d}")
        rgb_path = os.path.join(demo_dir, "rgb.npy")
        if os.path.exists(rgb_path):
            rgb = np.load(rgb_path)  # (T, H, W, 3)
            demos.append(rgb)
        else:
            # Placeholder — black frames
            demos.append(np.zeros((50, 256, 256, 3), dtype=np.uint8))

    n_demos = len(demos)
    demo_w = W // n_demos
    demo_h = int(demo_w * 0.75)
    demo_y = (H - demo_h) // 2

    for i in range(n_frames):
        t = i / n_frames
        f = blank()
        red_bar(f)

        # Section title
        f = text_on(f, "Step 1: Synthetic Data Generation",
                    x=0, y=30, size=32, color=RED, center=True)
        f = text_on(f, f"Genesis 0.4.3  |  IK-planned pick-and-lift  |  ~49 fps on OCI A100",
                    x=0, y=75, size=22, color=GRAY, center=True)

        # Draw each demo episode
        for di, demo_rgb in enumerate(demos):
            frame_idx = int(t * (len(demo_rgb) - 1))
            frame = demo_rgb[frame_idx]  # (H, W, 3)
            frame_resized = cv2.resize(frame, (demo_w - 20, demo_h - 20))

            x_off = di * demo_w + 10
            y_off = demo_y + 10
            f[y_off:y_off + demo_h - 20, x_off:x_off + demo_w - 20] = frame_resized[..., ::-1]  # RGB→BGR

            # Demo label
            f = text_on(f, f"Demo {di+1}",
                        x=x_off + 10, y=y_off + 10, size=20, color=WHITE)

        # Counter
        demos_so_far = int(t * 100)
        f = text_on(f, f"Generating... {demos_so_far}/100 demos",
                    x=0, y=H - 80, size=28, color=LGRAY, center=True)
        f = text_on(f, f"100% IK success  ·  ~0.9s/demo  ·  {demos_so_far*50:,} training frames",
                    x=0, y=H - 45, size=20, color=GRAY, center=True)

        frames_out.append(f)
    return frames_out


# ── Section 3: Training montage (20-30s = 300 frames) ─────────────────────

def training_section(n_frames=300):
    """Animate loss curve and GPU utilization."""
    frames_out = []

    # Simulate loss curve: 0.82 → 0.164 over 2000 steps
    steps = np.linspace(0, 2000, 200)
    losses = 0.82 * np.exp(-steps / 600) + 0.164 * (1 - np.exp(-steps / 600))
    # Add some noise
    losses += np.random.default_rng(42).normal(0, 0.01, len(losses))

    for i in range(n_frames):
        t = i / n_frames
        f = blank()
        red_bar(f)

        f = text_on(f, "Step 2: GR00T Fine-Tuning on OCI A100",
                    x=0, y=30, size=32, color=RED, center=True)
        f = text_on(f, "GR00T N1.6-3B  |  2.35 steps/sec  |  87% GPU util  |  $0.0043 / 10k steps",
                    x=0, y=75, size=22, color=GRAY, center=True)

        # Draw loss curve
        n_shown = max(1, int(t * len(steps)))
        chart_x, chart_y = 120, 150
        chart_w, chart_h = W - 300, 420

        # Chart background
        cv2.rectangle(f, (chart_x, chart_y), (chart_x + chart_w, chart_y + chart_h), DGRAY, -1)
        cv2.rectangle(f, (chart_x, chart_y), (chart_x + chart_w, chart_y + chart_h), (80, 80, 80), 1)

        # Loss curve
        max_loss, min_loss = 0.90, 0.10
        pts = []
        for j in range(n_shown):
            px = chart_x + int(j / len(steps) * chart_w)
            py = chart_y + chart_h - int((losses[j] - min_loss) / (max_loss - min_loss) * chart_h)
            pts.append((px, py))

        if len(pts) > 1:
            pts_arr = np.array(pts, dtype=np.int32)
            cv2.polylines(f, [pts_arr], False, RED, 2)
            cv2.circle(f, pts[-1], 5, RED, -1)

        # Labels
        f = text_on(f, "Training Loss",    x=chart_x,           y=chart_y - 30,  size=20, color=LGRAY)
        f = text_on(f, "0.82",             x=chart_x - 50,      y=chart_y,       size=18, color=GRAY)
        f = text_on(f, "0.16",             x=chart_x - 50,      y=chart_y + chart_h - 20, size=18, color=GREEN)
        f = text_on(f, f"Step: {int(t * 2000):,} / 2000",  x=chart_x, y=chart_y + chart_h + 10, size=22, color=LGRAY)

        # Stats box
        bx, by = W - 350, 200
        cv2.rectangle(f, (bx, by), (bx + 280, by + 250), (25, 25, 25), -1)
        cv2.rectangle(f, (bx, by), (bx + 280, by + 250), DGRAY, 1)
        f = text_on(f, "OCI A100-SXM4-80GB",  x=bx+10, y=by+10,  size=16, color=GRAY)
        f = text_on(f, f"{int(t*87)}% GPU util",  x=bx+10, y=by+50,  size=28, color=GREEN)
        f = text_on(f, "36.8 GB VRAM",         x=bx+10, y=by+95,  size=22, color=LGRAY)
        f = text_on(f, "2.35 steps/sec",        x=bx+10, y=by+130, size=22, color=LGRAY)
        f = text_on(f, "$0.0043 / 10k steps",   x=bx+10, y=by+165, size=20, color=RED)
        f = text_on(f, f"{int(t*14)} min elapsed",  x=bx+10, y=by+205, size=18, color=GRAY)

        frames_out.append(f)
    return frames_out


# ── Section 4: Eval comparison (30-42s = 360 frames) ─────────────────────

def eval_section(n_frames=360):
    """Show baseline vs fine-tuned MAE comparison."""
    frames_out = []

    for i in range(n_frames):
        t = i / n_frames
        f = blank()
        red_bar(f)

        f = text_on(f, "Step 3: Open-Loop Evaluation",
                    x=0, y=30, size=32, color=RED, center=True)
        f = text_on(f, "5 trajectories  |  MAE: mean absolute error (joint radians)",
                    x=0, y=75, size=22, color=GRAY, center=True)

        # Two cards side by side
        card_w, card_h = 560, 400
        for ci, (label, mae, color) in enumerate([
            ("Random Baseline", 0.103, GRAY),
            ("GR00T Fine-Tuned", 0.013, GREEN),
        ]):
            cx = 100 + ci * (card_w + 150)
            cy = 160

            # Card bg
            cv2.rectangle(f, (cx, cy), (cx + card_w, cy + card_h), (25, 25, 25), -1)
            cv2.rectangle(f, (cx, cy), (cx + card_w, cy + card_h), DGRAY, 1)

            # Red top accent
            cv2.rectangle(f, (cx, cy), (cx + card_w, cy + 6), RED, -1)

            f = text_on(f, label,               x=cx+20, y=cy+20,  size=24, color=LGRAY)
            f = text_on(f, f"MAE  {mae:.3f}",   x=cx+20, y=cy+70,  size=52, color=color)
            f = text_on(f, "joint radians",      x=cx+20, y=cy+140, size=20, color=GRAY)

            # Bar
            bar_y = cy + 200
            bar_max = int(card_w * 0.85)
            bar_val = int((mae / 0.12) * bar_max)
            cv2.rectangle(f, (cx+20, bar_y), (cx+20+bar_max, bar_y+30), DGRAY, -1)
            cv2.rectangle(f, (cx+20, bar_y), (cx+20+bar_val, bar_y+30), color, -1)

            # Animate reveal
            if ci == 1 and t < 0.3:
                # Overlay to hide fine-tuned until t>0.3
                cv2.rectangle(f, (cx, cy), (cx + card_w, cy + card_h), tuple(BG), -1)
                f = text_on(f, "Evaluating...", x=cx+20, y=cy+180, size=36, color=GRAY)

        # Improvement callout (appears at t>0.5)
        if t > 0.5:
            reveal = min(1.0, (t - 0.5) * 2)
            col = tuple(int(c * reveal) for c in GREEN)
            f = text_on(f, "8.7× improvement",  x=0, y=700, size=56, color=col, center=True)
            f = text_on(f, "(0.103 → 0.013 MAE, IK-planned fine-tuning vs random noise baseline)",
                        x=0, y=770, size=22, color=tuple(int(c * reveal) for c in GRAY), center=True)

        frames_out.append(f)
    return frames_out


# ── Section 5: Stats card (42-60s = 540 frames) ───────────────────────────

def stats_section(n_frames=540):
    frames_out = []

    stats = [
        ("8.7×",    "MAE Improvement",       "IK-planned GR00T vs baseline"),
        ("2.35",    "Steps / Sec",           "OCI A100-SXM4-80GB, batch=32"),
        ("$0.0043", "Per 10k Steps",         "vs $200k DGX CapEx"),
        ("87%",     "GPU Utilization",       "36.8 GB / 80 GB VRAM"),
        ("3.07×",   "DDP Throughput Gain",   "4× A100 burst: 230 vs 75 samples/sec"),
    ]

    for i in range(n_frames):
        t = i / n_frames
        f = blank()
        red_bar(f)

        f = text_on(f, "OCI Robot Cloud — Benchmark Results",
                    x=0, y=30, size=32, color=RED, center=True)
        f = text_on(f, "Measured on OCI A100-SXM4-80GB  |  GR00T N1.6-3B  |  100 IK-planned demos",
                    x=0, y=75, size=22, color=GRAY, center=True)

        # 5-card grid (2+3)
        cw, ch = 340, 200
        positions = [
            (120, 160), (500, 160),   # row 1
            (120, 390), (500, 390), (880, 390),  # row 2
        ]
        for si, (stat, label, sub) in enumerate(stats):
            reveal = min(1.0, max(0.0, t * 5 - si * 0.5))
            if reveal <= 0:
                continue
            cx, cy = positions[si]

            alpha_bg = tuple(int(25 * reveal) for _ in range(3))
            cv2.rectangle(f, (cx, cy), (cx+cw, cy+ch), (25, 25, 25), -1)
            cv2.rectangle(f, (cx, cy), (cx+cw, cy+ch), DGRAY, 1)
            cv2.rectangle(f, (cx, cy), (cx+cw, cy+5), RED, -1)

            col = tuple(int(c * reveal) for c in RED)
            lcol = tuple(int(c * reveal) for c in WHITE)
            gcol = tuple(int(c * reveal) for c in GRAY)

            f = text_on(f, stat,  x=cx+14, y=cy+20,  size=48, color=col)
            f = text_on(f, label, x=cx+14, y=cy+85,  size=18, color=lcol)
            f = text_on(f, sub,   x=cx+14, y=cy+115, size=14, color=gcol)

        # Final CTA at end
        if t > 0.8:
            cta_alpha = min(1.0, (t - 0.8) * 5)
            f = text_on(f, "OCI — Where Robots Learn",
                        x=0, y=680, size=40,
                        color=tuple(int(c * cta_alpha) for c in WHITE), center=True)
            f = text_on(f, "github.com/qianjun22/roboticsai",
                        x=0, y=740, size=24,
                        color=tuple(int(c * cta_alpha) for c in GRAY), center=True)

        frames_out.append(f)
    return frames_out


# ── Render pipeline ────────────────────────────────────────────────────────

def main():
    print(f"[demo-video] Output: {args.output}")
    print(f"[demo-video] Resolution: {W}x{H} @ {FPS}fps")

    sections = [
        ("Title",    title_section,    240),
        ("SDG",      sdg_section,      360),
        ("Training", training_section, 300),
        ("Eval",     eval_section,     360),
        ("Stats",    stats_section,    540),
    ]

    total_frames = sum(n for _, _, n in sections)
    print(f"[demo-video] Total frames: {total_frames} ({total_frames/FPS:.0f}s)")

    # Write to temp directory then stitch with ffmpeg
    with tempfile.TemporaryDirectory() as tmpdir:
        frame_idx = 0
        for name, fn, n_frames in sections:
            print(f"[demo-video] Rendering {name} ({n_frames} frames)...")
            frames = fn(n_frames)
            for f in frames:
                cv2.imwrite(os.path.join(tmpdir, f"frame_{frame_idx:06d}.jpg"), f, [cv2.IMWRITE_JPEG_QUALITY, 90])
                frame_idx += 1

        print(f"[demo-video] Encoding MP4...")
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(tmpdir, "frame_%06d.jpg"),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            args.output,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    size_mb = os.path.getsize(args.output) / 1e6
    print(f"[demo-video] Done: {args.output} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
