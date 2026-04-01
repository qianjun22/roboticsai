import datetime
import fastapi
import uvicorn
PORT = 44783
SERVICE = "robotics-object_pose_estimator-9188"
DESCRIPTION = "GTM object pose estimator service cycle 9188"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
