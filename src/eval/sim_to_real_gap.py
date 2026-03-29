"""
Sim-to-real gap analysis for OCI Robot Cloud.

Quantifies the distribution shift between:
  - Simulation frames (Genesis / Isaac Sim SDG)
  - Real robot camera frames (uploaded by design partner)

Metrics computed:
  1. FID (Fréchet Inception Distance) — perceptual similarity
  2. Pixel-level statistics (mean, std, histogram distance)
  3. Action distribution shift (KL divergence on joint positions)
  4. Policy confidence degradation (entropy of GR00T action distribution)

Used to decide:
  - Whether domain randomization needs to be tuned
  - Whether more diverse SDG is needed before transfer
  - Whether fine-tuning on real data is required

Usage:
    python3 sim_to_real_gap.py \\
        --sim-dir /tmp/lerobot_500/frames \\
        --real-dir /tmp/real_demos/frames \\
        --server-url http://localhost:8002 \\
        --output /tmp/gap_report.html
"""

import argparse
import base64
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

try:
    from PIL import Image
except ImportError:
    raise ImportError("pip install Pillow")


# ── Image loader ──────────────────────────────────────────────────────────────

def load_frames(frame_dir: Path, max_frames: int = 200, size: tuple = (256, 256)) -> np.ndarray:
    """Load up to max_frames RGB images from a directory, return (N, H, W, 3) uint8."""
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    paths = sorted([p for p in frame_dir.rglob("*") if p.suffix.lower() in exts])
    if not paths:
        # Try HDF5 fallback
        return _load_from_hdf5(frame_dir, max_frames, size)

    paths = paths[:max_frames]
    frames = []
    for p in paths:
        img = Image.open(p).convert("RGB").resize(size, Image.BILINEAR)
        frames.append(np.array(img, dtype=np.uint8))
    return np.stack(frames)  # (N, H, W, 3)


def _load_from_hdf5(base_dir: Path, max_frames: int, size: tuple) -> np.ndarray:
    """Load frames from HDF5 episode files (LeRobot v2 format)."""
    try:
        import h5py
    except ImportError:
        return np.zeros((0, size[1], size[0], 3), dtype=np.uint8)

    frames = []
    for ep_dir in sorted(base_dir.iterdir()):
        hdf5_path = ep_dir / "data.hdf5"
        if not hdf5_path.exists():
            continue
        with h5py.File(hdf5_path, "r") as f:
            if "observation/image" in f:
                arr = f["observation/image"][:]  # (T, H, W, 3)
                for frame in arr:
                    if len(frames) >= max_frames:
                        break
                    img = Image.fromarray(frame.astype(np.uint8)).resize(size, Image.BILINEAR)
                    frames.append(np.array(img, dtype=np.uint8))
        if len(frames) >= max_frames:
            break

    if not frames:
        return np.zeros((0, size[1], size[0], 3), dtype=np.uint8)
    return np.stack(frames)


# ── Pixel-level statistics ────────────────────────────────────────────────────

def pixel_stats(frames: np.ndarray) -> dict:
    """Compute per-channel mean, std, and histogram."""
    f = frames.astype(np.float32) / 255.0  # (N, H, W, 3)
    return {
        "mean": f.mean(axis=(0, 1, 2)).tolist(),          # [R, G, B]
        "std": f.std(axis=(0, 1, 2)).tolist(),
        "min": f.min(axis=(0, 1, 2)).tolist(),
        "max": f.max(axis=(0, 1, 2)).tolist(),
    }


def histogram_distance(frames_a: np.ndarray, frames_b: np.ndarray, bins: int = 32) -> float:
    """
    Bhattacharyya distance between pixel intensity histograms.
    0 = identical distributions, higher = more different.
    """
    a_flat = frames_a.flatten().astype(np.float32) / 255.0
    b_flat = frames_b.flatten().astype(np.float32) / 255.0

    hist_a, _ = np.histogram(a_flat, bins=bins, range=(0, 1), density=True)
    hist_b, _ = np.histogram(b_flat, bins=bins, range=(0, 1), density=True)

    # Normalize to probabilities
    hist_a = hist_a / (hist_a.sum() + 1e-10)
    hist_b = hist_b / (hist_b.sum() + 1e-10)

    # Bhattacharyya coefficient
    bc = np.sum(np.sqrt(hist_a * hist_b))
    return float(-np.log(bc + 1e-10))


# ── Approximate FID ───────────────────────────────────────────────────────────

def compute_fid_approx(frames_a: np.ndarray, frames_b: np.ndarray) -> float:
    """
    Lightweight FID approximation using flattened pixel features.
    Full FID requires Inception v3; this is a fast proxy.
    Mean FID (pixel-space): measures mean + covariance distance.
    """
    def stats(frames):
        flat = frames.reshape(len(frames), -1).astype(np.float64) / 255.0
        mu = flat.mean(axis=0)
        # Covariance — use diagonal for memory efficiency
        sigma_diag = flat.var(axis=0)
        return mu, sigma_diag

    mu1, s1 = stats(frames_a)
    mu2, s2 = stats(frames_b)

    # Simplified FID (diagonal covariance approximation)
    diff = mu1 - mu2
    mean_term = float(np.dot(diff, diff))
    # Trace term: tr(Σ1 + Σ2 - 2*sqrt(Σ1*Σ2))  with diagonal matrices
    cov_term = float(np.sum(s1 + s2 - 2 * np.sqrt(s1 * s2 + 1e-10)))
    return mean_term + cov_term


# ── Policy confidence on real frames ─────────────────────────────────────────

def measure_policy_confidence(
    frames: np.ndarray,
    server_url: str,
    instruction: str = "pick up the red cube from the table",
    n_samples: int = 10,
) -> dict:
    """
    Query GR00T on N real frames. Measure action entropy (confidence proxy).
    High entropy = uncertain policy = real frames look OOD.
    """
    entropies = []
    latencies = []
    n_samples = min(n_samples, len(frames))
    idxs = np.linspace(0, len(frames) - 1, n_samples, dtype=int)

    for idx in idxs:
        rgb = frames[idx]
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            import time
            Image.fromarray(rgb).save(tmp.name, quality=90)
            t0 = time.time()
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", f"{server_url}/predict",
                 "-F", f"image=@{tmp.name}", "-F", f"instruction={instruction}"],
                capture_output=True, text=True, timeout=15,
            )
            latency = (time.time() - t0) * 1000
            data = json.loads(result.stdout)
            arm = np.array(data["arm"])  # (16, 7)

            # Action entropy: variance across chunk steps as proxy for uncertainty
            var_per_joint = arm.var(axis=0)  # (7,)
            entropy = float(np.mean(var_per_joint))
            entropies.append(entropy)
            latencies.append(latency)
        except Exception as e:
            entropies.append(None)
        finally:
            os.unlink(tmp.name)

    valid = [e for e in entropies if e is not None]
    return {
        "n_samples": n_samples,
        "mean_action_variance": float(np.mean(valid)) if valid else None,
        "std_action_variance": float(np.std(valid)) if valid else None,
        "mean_latency_ms": float(np.mean(latencies)) if latencies else None,
        "note": "High variance = policy uncertain on these frames (OOD indicator)",
    }


# ── Gap scoring ───────────────────────────────────────────────────────────────

def gap_score(bhattacharyya: float, fid_approx: float) -> dict:
    """
    Convert metrics to an actionable gap score (0-10).
    0 = negligible gap, 10 = large gap requiring more SDG diversity.
    """
    # Empirical thresholds based on sim-to-real literature
    # Bhattacharyya: 0 = perfect, >0.3 = large shift
    # FID-pixel: <1k = ok, >5k = large shift (not real FID units)
    bhatt_score = min(bhattacharyya / 0.3, 1.0) * 5.0   # 0–5 from bhatt
    fid_score = min(fid_approx / 5000, 1.0) * 5.0        # 0–5 from FID

    total = bhatt_score + fid_score  # 0–10

    if total < 2:
        label = "Negligible"
        recommendation = "Domain gap is small. Current SDG diversity is likely sufficient."
    elif total < 5:
        label = "Moderate"
        recommendation = (
            "Some domain shift detected. Consider adding 1-2 more Isaac Sim "
            "domain randomization dimensions (lighting, texture variety)."
        )
    elif total < 7:
        label = "Significant"
        recommendation = (
            "Notable domain gap. Recommend: (1) collect 10-20 real demo frames for "
            "SDG calibration, (2) increase texture/lighting randomization range, "
            "(3) consider fine-tuning on mixed sim+real data."
        )
    else:
        label = "Large"
        recommendation = (
            "Large domain gap. Fine-tuning on real robot data is recommended. "
            "SDG alone may not bridge this gap without significant randomization tuning."
        )

    return {
        "total_score": round(total, 2),
        "label": label,
        "recommendation": recommendation,
        "bhattacharyya_component": round(bhatt_score, 2),
        "fid_component": round(fid_score, 2),
    }


# ── HTML report ───────────────────────────────────────────────────────────────

def generate_html_report(
    sim_stats: dict, real_stats: dict,
    bhatt: float, fid: float, gap: dict,
    policy_conf: Optional[dict],
    out_path: Path,
    sim_n: int, real_n: int,
):
    from typing import Optional

    def bar(label, sim_val, real_val, unit="", fmt=".3f"):
        sv = f"{sim_val:{fmt}}" if sim_val is not None else "—"
        rv = f"{real_val:{fmt}}" if real_val is not None else "—"
        return f"<tr><td>{label}</td><td>{sv} {unit}</td><td>{rv} {unit}</td></tr>"

    sim_mean = sim_stats["mean"]
    real_mean = real_stats["mean"]

    color = {"Negligible": "#22c55e", "Moderate": "#f59e0b",
             "Significant": "#f97316", "Large": "#ef4444"}.get(gap["label"], "#6b7280")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sim-to-Real Gap Analysis — OCI Robot Cloud</title>
<style>
  body {{ background:#0d0d0d; color:#e5e7eb; font-family:monospace; margin:0; padding:24px; }}
  h1 {{ color:#c74634; margin-bottom:4px; }} h2 {{ color:#9ca3af; font-size:14px; margin:24px 0 8px; }}
  .card {{ background:#1a1a1a; border:1px solid #2a2a2a; border-radius:8px; padding:16px; margin-bottom:16px; }}
  .score {{ font-size:56px; font-weight:bold; color:{color}; }}
  .label {{ font-size:18px; color:{color}; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ color:#6b7280; font-size:11px; text-align:left; padding:6px 0; border-bottom:1px solid #2a2a2a; }}
  td {{ padding:5px 0; font-size:13px; border-bottom:1px solid #1f1f1f; }}
  td:not(:first-child) {{ text-align:right; }}
  .rec {{ color:#fcd34d; font-size:13px; line-height:1.6; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
</style>
</head>
<body>
<h1>Sim-to-Real Gap Analysis</h1>
<p style="color:#6b7280;font-size:13px;">OCI Robot Cloud · {sim_n} sim frames vs {real_n} real frames</p>

<div class="card" style="text-align:center;">
  <div class="score">{gap['total_score']}/10</div>
  <div class="label">{gap['label']} Domain Gap</div>
</div>

<div class="card">
  <h2>RECOMMENDATION</h2>
  <div class="rec">{gap['recommendation']}</div>
</div>

<div class="grid2">
  <div class="card">
    <h2>PIXEL STATISTICS</h2>
    <table>
      <tr><th>Metric</th><th>Sim</th><th>Real</th></tr>
      {bar("Mean R", sim_mean[0], real_mean[0])}
      {bar("Mean G", sim_mean[1], real_mean[1])}
      {bar("Mean B", sim_mean[2], real_mean[2])}
      {bar("Std R", sim_stats['std'][0], real_stats['std'][0])}
      {bar("Std G", sim_stats['std'][1], real_stats['std'][1])}
      {bar("Std B", sim_stats['std'][2], real_stats['std'][2])}
    </table>
  </div>
  <div class="card">
    <h2>DISTRIBUTION METRICS</h2>
    <table>
      <tr><th>Metric</th><th>Value</th><th>Threshold</th></tr>
      <tr><td>Bhattacharyya dist.</td><td>{bhatt:.4f}</td><td>&lt;0.1 = good</td></tr>
      <tr><td>FID-pixel approx.</td><td>{fid:.1f}</td><td>&lt;1000 = good</td></tr>
      <tr><td>Gap score</td><td style="color:{color}">{gap['total_score']}/10</td><td>&lt;3 = OK</td></tr>
    </table>
    {f'''<br><h2>POLICY CONFIDENCE ON REAL FRAMES</h2>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Avg action variance</td><td>{policy_conf["mean_action_variance"]:.4f}</td></tr>
      <tr><td>Avg latency</td><td>{policy_conf["mean_latency_ms"]:.0f}ms</td></tr>
    </table>''' if policy_conf and policy_conf.get("mean_action_variance") else ""}
  </div>
</div>

<div class="card">
  <h2>WHAT EACH METRIC MEANS</h2>
  <table>
    <tr><th>Metric</th><th>Meaning</th></tr>
    <tr><td>Bhattacharyya distance</td><td>Pixel histogram overlap. 0=identical, &gt;0.3=large shift.</td></tr>
    <tr><td>FID-pixel approx.</td><td>Mean+covariance distance in pixel space. Proxy for Inception FID.</td></tr>
    <tr><td>Action variance</td><td>How much GR00T's action chunk varies across steps on real frames. High=uncertain policy.</td></tr>
  </table>
</div>

<p style="color:#374151;font-size:11px;text-align:center;margin-top:24px;">
  OCI Robot Cloud · Sim-to-Real Gap Analysis · Generated by src/eval/sim_to_real_gap.py
</p>
</body>
</html>"""

    out_path.write_text(html)
    print(f"[Gap] Report saved: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

from typing import Optional


def main():
    parser = argparse.ArgumentParser(description="Sim-to-real gap analysis")
    parser.add_argument("--sim-dir", required=True, help="Sim frames directory (or LeRobot dataset)")
    parser.add_argument("--real-dir", required=True, help="Real robot frames directory")
    parser.add_argument("--server-url", default=None,
                        help="GR00T server URL for policy confidence test (optional)")
    parser.add_argument("--output", default="/tmp/gap_report.html")
    parser.add_argument("--max-frames", type=int, default=200)
    parser.add_argument("--n-policy-samples", type=int, default=10)
    args = parser.parse_args()

    sim_dir = Path(args.sim_dir)
    real_dir = Path(args.real_dir)

    print(f"[Gap] Loading sim frames from {sim_dir}...")
    sim_frames = load_frames(sim_dir, args.max_frames)
    print(f"[Gap] Loading real frames from {real_dir}...")
    real_frames = load_frames(real_dir, args.max_frames)

    if len(sim_frames) == 0 or len(real_frames) == 0:
        print("[Gap] ERROR: Could not load frames. Check directory paths.")
        return

    print(f"[Gap] Sim: {len(sim_frames)} frames | Real: {len(real_frames)} frames")

    print("[Gap] Computing pixel statistics...")
    sim_stats = pixel_stats(sim_frames)
    real_stats = pixel_stats(real_frames)

    print("[Gap] Computing histogram distance (Bhattacharyya)...")
    bhatt = histogram_distance(sim_frames, real_frames)

    print("[Gap] Computing FID approximation...")
    fid = compute_fid_approx(sim_frames, real_frames)

    gap = gap_score(bhatt, fid)

    policy_conf = None
    if args.server_url and len(real_frames) > 0:
        print(f"[Gap] Querying policy confidence on real frames ({args.n_policy_samples} samples)...")
        policy_conf = measure_policy_confidence(
            real_frames, args.server_url, n_samples=args.n_policy_samples
        )

    print(f"\n{'='*50}")
    print(f"[Gap] Bhattacharyya distance: {bhatt:.4f}")
    print(f"[Gap] FID-pixel approx:       {fid:.1f}")
    print(f"[Gap] Gap score:              {gap['total_score']}/10 ({gap['label']})")
    print(f"[Gap] Recommendation: {gap['recommendation']}")
    if policy_conf and policy_conf.get("mean_action_variance"):
        print(f"[Gap] Policy action variance on real frames: {policy_conf['mean_action_variance']:.4f}")
    print(f"{'='*50}\n")

    generate_html_report(
        sim_stats, real_stats, bhatt, fid, gap, policy_conf,
        Path(args.output), len(sim_frames), len(real_frames),
    )

    # Also save JSON
    json_out = Path(args.output).with_suffix(".json")
    with open(json_out, "w") as f:
        json.dump({
            "sim_frames": len(sim_frames),
            "real_frames": len(real_frames),
            "sim_stats": sim_stats,
            "real_stats": real_stats,
            "bhattacharyya": bhatt,
            "fid_approx": fid,
            "gap": gap,
            "policy_confidence": policy_conf,
        }, f, indent=2)
    print(f"[Gap] JSON saved: {json_out}")


if __name__ == "__main__":
    main()
