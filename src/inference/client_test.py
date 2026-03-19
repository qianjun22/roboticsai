"""
Quick test client for the OCI Robot Cloud inference server.

Usage:
    # Test with a local image
    python client_test.py --image path/to/image.jpg --instruction "pick up the red block"

    # Test with a generated dummy image (no real image needed)
    python client_test.py --dummy --instruction "move arm to the right"

    # Latency benchmark (N requests)
    python client_test.py --dummy --instruction "pick up the cup" --benchmark 50
"""

import argparse
import io
import time

import httpx
import numpy as np
from PIL import Image


def dummy_image_bytes(width=224, height=224) -> bytes:
    """Generate a random RGB image as JPEG bytes."""
    arr = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def predict(base_url: str, image_bytes: bytes, instruction: str) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{base_url}/predict",
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            data={"instruction": instruction},
        )
        resp.raise_for_status()
        return resp.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--image", help="Path to image file")
    p.add_argument("--dummy", action="store_true", help="Use random dummy image")
    p.add_argument("--instruction", default="pick up the red block")
    p.add_argument("--benchmark", type=int, default=0, help="Run N requests and report stats")
    args = p.parse_args()

    # Health check
    with httpx.Client() as client:
        health = client.get(f"{args.url}/health").json()
        print(f"Server: {health}")

    # Prepare image
    if args.dummy:
        image_bytes = dummy_image_bytes()
        print("Using dummy random image")
    elif args.image:
        with open(args.image, "rb") as f:
            image_bytes = f.read()
        print(f"Using image: {args.image}")
    else:
        print("Provide --image or --dummy")
        return

    if args.benchmark > 0:
        print(f"\nBenchmark: {args.benchmark} requests...")
        latencies = []
        for i in range(args.benchmark):
            t0 = time.perf_counter()
            result = predict(args.url, image_bytes, args.instruction)
            latencies.append((time.perf_counter() - t0) * 1000)
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{args.benchmark} done")

        latencies = sorted(latencies)
        print(f"\nLatency over {args.benchmark} requests:")
        print(f"  p50:  {latencies[len(latencies)//2]:.1f}ms")
        print(f"  p95:  {latencies[int(len(latencies)*0.95)]:.1f}ms")
        print(f"  p99:  {latencies[int(len(latencies)*0.99)]:.1f}ms")
        print(f"  mean: {sum(latencies)/len(latencies):.1f}ms")
    else:
        result = predict(args.url, image_bytes, args.instruction)
        print(f"\nInstruction: {result['instruction']}")
        print(f"Action:      {[round(a, 4) for a in result['action']]}")
        print(f"  [dx={result['action'][0]:.4f}, dy={result['action'][1]:.4f}, dz={result['action'][2]:.4f}]")
        print(f"  [droll={result['action'][3]:.4f}, dpitch={result['action'][4]:.4f}, dyaw={result['action'][5]:.4f}]")
        print(f"  [gripper={'open' if result['action'][6] > 0.5 else 'close'} ({result['action'][6]:.4f})]")
        print(f"Latency:     {result['latency_ms']}ms")


if __name__ == "__main__":
    main()
