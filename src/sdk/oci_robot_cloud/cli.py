"""
oci-robot-cloud CLI
====================
Command-line interface for OCI Robot Cloud operations.

Usage:
    oci-robot-cloud train --task "pick red cube" --robot franka --data ./demos
    oci-robot-cloud status <job_id>
    oci-robot-cloud results <job_id>
    oci-robot-cloud deploy <job_id>
    oci-robot-cloud inspect ./demos
    oci-robot-cloud pricing
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .client import RobotCloudClient
from .data_utils import inspect


def _make_client(args) -> RobotCloudClient:
    endpoint = args.endpoint or os.environ.get("OCI_ROBOT_CLOUD_ENDPOINT", "http://localhost:8080")
    api_key = args.api_key or os.environ.get("OCI_ROBOT_CLOUD_API_KEY", "")
    return RobotCloudClient(endpoint=endpoint, api_key=api_key)


def cmd_train(args):
    client = _make_client(args)
    job = client.train(
        task=args.task,
        robot=args.robot,
        data_path=args.data,
        num_demos=args.num_demos,
        max_steps=args.max_steps,
    )
    print(f"[train] Job submitted: {job.job_id}")
    if args.wait:
        print(f"[train] Waiting for completion (poll every 30s)...")
        result = client.wait(job.job_id)
        print(json.dumps({
            "job_id": result.job_id,
            "status": result.status,
            "metrics": result.metrics,
            "cost_usd": result.cost_usd,
        }, indent=2))
    else:
        print(f"[train] Check status: oci-robot-cloud status {job.job_id}")


def cmd_status(args):
    client = _make_client(args)
    s = client.status(args.job_id)
    print(json.dumps(s, indent=2))


def cmd_results(args):
    client = _make_client(args)
    result = client.results(args.job_id)
    print(json.dumps({
        "job_id": result.job_id,
        "status": result.status,
        "metrics": result.metrics,
        "cost_usd": result.cost_usd,
        "checkpoint_url": result.checkpoint_url,
        "report_url": result.report_url,
    }, indent=2))


def cmd_deploy(args):
    client = _make_client(args)
    pkg = client.deploy_to_jetson(args.job_id)
    print(f"[deploy] Package ready: {pkg.download_url}")
    print(f"[deploy] Size: {pkg.size_mb:.1f} MB")
    if pkg.instructions:
        print(f"\n{pkg.instructions}")


def cmd_pricing(args):
    client = _make_client(args)
    p = client.pricing()
    print(f"GPU:               {p.gpu}")
    print(f"Region:            {p.region}")
    print(f"Cost per hour:     ${p.cost_per_hour:.2f}")
    print(f"Cost per 10k steps: ${p.cost_per_10k_steps:.4f}")


def cmd_inspect(args):
    stats = inspect(args.data_path)
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="oci-robot-cloud",
        description="OCI Robot Cloud CLI — fine-tune GR00T on OCI A100",
    )
    parser.add_argument("--endpoint", help="API endpoint URL (or set OCI_ROBOT_CLOUD_ENDPOINT)")
    parser.add_argument("--api-key", help="API key (or set OCI_ROBOT_CLOUD_API_KEY)")

    sub = parser.add_subparsers(dest="command", required=True)

    # train
    p_train = sub.add_parser("train", help="Submit a fine-tuning job")
    p_train.add_argument("--task", required=True, help="Task description")
    p_train.add_argument("--robot", default="franka",
                         choices=["franka", "ur5e", "kinova_gen3", "xarm7"])
    p_train.add_argument("--data", help="Path to local episode directory")
    p_train.add_argument("--num-demos", type=int, default=100)
    p_train.add_argument("--max-steps", type=int, default=2000)
    p_train.add_argument("--wait", action="store_true", help="Wait for job completion")
    p_train.set_defaults(func=cmd_train)

    # status
    p_status = sub.add_parser("status", help="Check job status")
    p_status.add_argument("job_id")
    p_status.set_defaults(func=cmd_status)

    # results
    p_results = sub.add_parser("results", help="Fetch job results")
    p_results.add_argument("job_id")
    p_results.set_defaults(func=cmd_results)

    # deploy
    p_deploy = sub.add_parser("deploy", help="Package checkpoint for Jetson AGX Orin")
    p_deploy.add_argument("job_id")
    p_deploy.set_defaults(func=cmd_deploy)

    # pricing
    p_pricing = sub.add_parser("pricing", help="Show current compute pricing")
    p_pricing.set_defaults(func=cmd_pricing)

    # inspect
    p_inspect = sub.add_parser("inspect", help="Inspect a local episode dataset")
    p_inspect.add_argument("data_path", help="Path to episode directory")
    p_inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
