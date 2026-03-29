"""
OCI Robot Cloud SDK
===================
Synthetic data generation, GR00T fine-tuning, and edge deployment for robotics.

Quick start:
    pip install oci-robot-cloud

    from oci_robot_cloud import RobotCloudClient

    client = RobotCloudClient(
        endpoint="https://robotcloud.oci.oraclecloud.com",
        api_key="<your-api-key>",
    )
    job = client.train(task="pick up the red widget", robot="franka", data_path="./demos")
    result = client.wait(job.job_id)
    print(result.metrics)   # {"mae": 0.013, "cost_usd": 0.0086}
"""

from .client import RobotCloudClient, TrainJob, TrainResult  # noqa: F401

__version__ = "0.9.0"
__all__ = ["RobotCloudClient", "TrainJob", "TrainResult"]
