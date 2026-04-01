import datetime
import fastapi
import uvicorn
PORT = 43751
SERVICE = "robotics-force-torque-monitor-8930"
DESCRIPTION = "GTM force torque monitor service cycle 8930"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
