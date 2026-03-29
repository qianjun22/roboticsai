"""
OCI Robot Cloud — GR00T N1.6 Inference Server

Serves NVIDIA GR00T N1.6 (3B vision-language-action model) as a REST API.
Input:  camera image + optional joint states + natural language instruction
Output: 16-step action chunk for left_arm, right_arm, left_hand, right_hand, waist

GR00T outputs 16 future action steps per inference call (action horizon=16).
The client should execute these sequentially before calling again.

Supported embodiments: gr1 (default), robocasa_panda_omron
Model: nvidia/GR00T-N1.6-3B (open weights, NVIDIA Noncommercial License)

Usage:
    # GPU 3 (leaving 0-2 for OpenVLA)
    cd ~/Isaac-GR00T
    source .venv/bin/activate
    CUDA_VISIBLE_DEVICES=3 python3 ~/roboticsai/src/inference/groot_server.py

    # Custom model path or embodiment
    CUDA_VISIBLE_DEVICES=3 python3 ~/roboticsai/src/inference/groot_server.py \\
        --model /home/ubuntu/models/GR00T-N1.6-3B \\
        --embodiment gr1 \\
        --port 8001
"""

import argparse
import io
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import gr00t.model  # noqa: F401 — registers GR00T model types with AutoModel
import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.policy.gr00t_policy import Gr00tPolicy
from PIL import Image
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("oci-robot-cloud-groot")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

policy: Optional[Gr00tPolicy] = None
embodiment_tag: Optional[EmbodimentTag] = None
_model_path: str = ""

# GR00T N1.6 / gr1 state dimensions
GR1_STATE_DIMS = {
    "left_arm": 7,
    "right_arm": 7,
    "left_hand": 6,
    "right_hand": 6,
    "waist": 3,
}


def load_model(model_path: str, embodiment: str) -> None:
    global policy, embodiment_tag, _model_path

    tag = EmbodimentTag[embodiment.upper()]
    log.info(f"Loading GR00T from {model_path} (embodiment={tag.value})")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    policy = Gr00tPolicy(
        embodiment_tag=tag,
        model_path=model_path,
        device=device,
    )
    embodiment_tag = tag
    _model_path = model_path
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    log.info(f"GR00T loaded. VRAM: {vram:.1f}GB")

    # Warmup inference
    log.info("Warming up model...")
    _dummy_inference()
    log.info("Warmup complete.")


def _dummy_inference() -> None:
    """Run a dummy inference to pre-compile CUDA kernels."""
    dummy_img = np.zeros((1, 1, 256, 256, 3), dtype=np.uint8)
    obs = _build_obs(dummy_img, "warmup", state_dict=None)
    policy.get_action(obs)


def _build_obs(
    img: np.ndarray,      # (1, 1, H, W, 3) uint8 RGB
    instruction: str,
    state_dict: Optional[dict],
) -> dict:
    """Build the observation dict in GR00T's expected format."""
    obs = {
        "video": {"ego_view_bg_crop_pad_res256_freq20": img},
        "language": {"task": [[instruction]]},
        "state": {},
    }

    if state_dict is not None:
        obs["state"] = {k: np.array(v, dtype=np.float32).reshape(1, 1, -1)
                        for k, v in state_dict.items()}
    else:
        # Zero state (uncontrolled baseline)
        obs["state"] = {k: np.zeros((1, 1, d), dtype=np.float32)
                        for k, d in GR1_STATE_DIMS.items()}

    return obs


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    args = app.state.args
    load_model(args.model, args.embodiment)
    yield


app = FastAPI(
    title="OCI Robot Cloud — GR00T N1.6 Inference API",
    description="16-step action chunk prediction for physical AI workloads",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ActionChunkResponse(BaseModel):
    # 16-step action horizon for each modality
    left_arm: list[list[float]]    # (16, 7)
    right_arm: list[list[float]]   # (16, 7)
    left_hand: list[list[float]]   # (16, 6)
    right_hand: list[list[float]]  # (16, 6)
    waist: list[list[float]]       # (16, 3)
    instruction: str
    latency_ms: float
    model: str
    embodiment: str


class HealthResponse(BaseModel):
    status: str
    model: str
    embodiment: str
    device: str
    gpu_memory_gb: Optional[float] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    gpu_mem = None
    if torch.cuda.is_available():
        gpu_mem = round(torch.cuda.memory_allocated() / 1e9, 2)
    return HealthResponse(
        status="ok",
        model=_model_path,
        embodiment=embodiment_tag.value if embodiment_tag else "unknown",
        device="cuda" if torch.cuda.is_available() else "cpu",
        gpu_memory_gb=gpu_mem,
    )


@app.post("/predict", response_model=ActionChunkResponse)
async def predict(
    image: UploadFile = File(..., description="Robot camera frame (JPEG/PNG, 256x256)"),
    instruction: str = Form(..., description="Natural language task instruction"),
    left_arm: Optional[str] = Form(None, description="Left arm joint positions (7 floats, comma-separated)"),
    right_arm: Optional[str] = Form(None, description="Right arm joint positions (7 floats, comma-separated)"),
    left_hand: Optional[str] = Form(None, description="Left hand joint positions (6 floats, comma-separated)"),
    right_hand: Optional[str] = Form(None, description="Right hand joint positions (6 floats, comma-separated)"),
    waist: Optional[str] = Form(None, description="Waist joint positions (3 floats, comma-separated)"),
):
    """
    Predict a 16-step action chunk from a camera image and instruction.

    Returns actions for the full 16-step horizon. Execute sequentially,
    then call again with the updated robot state.
    """
    if policy is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Load and resize image
    try:
        raw = await image.read()
        pil_image = Image.open(io.BytesIO(raw)).convert("RGB").resize((256, 256))
        img_np = np.array(pil_image, dtype=np.uint8)[np.newaxis, np.newaxis]  # (1,1,256,256,3)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # Parse optional joint states
    def parse_joints(s: Optional[str]) -> Optional[list]:
        if s is None:
            return None
        try:
            return [float(x.strip()) for x in s.split(",")]
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid joint state format: {s}")

    state_dict = None
    la = parse_joints(left_arm)
    ra = parse_joints(right_arm)
    lh = parse_joints(left_hand)
    rh = parse_joints(right_hand)
    ws = parse_joints(waist)
    if any(v is not None for v in [la, ra, lh, rh, ws]):
        state_dict = {
            "left_arm":   la or [0.0] * 7,
            "right_arm":  ra or [0.0] * 7,
            "left_hand":  lh or [0.0] * 6,
            "right_hand": rh or [0.0] * 6,
            "waist":      ws or [0.0] * 3,
        }

    # Run inference
    t0 = time.perf_counter()
    try:
        obs = _build_obs(img_np, instruction, state_dict)
        action_chunk, _ = policy.get_action(obs)
    except Exception as e:
        log.exception("Inference error")
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info(f"GR00T predicted action in {latency_ms:.1f}ms | '{instruction}'")

    def to_list(arr) -> list:
        return np.array(arr).squeeze(0).tolist()  # remove batch dim

    return ActionChunkResponse(
        left_arm=to_list(action_chunk["left_arm"]),
        right_arm=to_list(action_chunk["right_arm"]),
        left_hand=to_list(action_chunk["left_hand"]),
        right_hand=to_list(action_chunk["right_hand"]),
        waist=to_list(action_chunk["waist"]),
        instruction=instruction,
        latency_ms=round(latency_ms, 2),
        model=_model_path,
        embodiment=embodiment_tag.value,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="OCI Robot Cloud GR00T inference server")
    p.add_argument("--model",      default="/home/ubuntu/models/GR00T-N1.6-3B",
                   help="Path to GR00T N1.6 model (default: /home/ubuntu/models/GR00T-N1.6-3B)")
    p.add_argument("--embodiment", default="GR1",
                   help="Embodiment tag: GR1 | ROBOCASA_PANDA_OMRON (default: GR1)")
    p.add_argument("--port",       type=int, default=8001)
    p.add_argument("--host",       default="0.0.0.0")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app.state.args = args
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
