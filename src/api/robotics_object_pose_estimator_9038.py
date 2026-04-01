import datetime
import fastapi
import uvicorn
PORT = 44183
SERVICE = "robotics-object_pose_estimator-9038"
DESCRIPTION = "GTM object pose estimator service cycle 9038"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
