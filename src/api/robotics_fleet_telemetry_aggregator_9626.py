import datetime
import fastapi
import uvicorn
PORT = 46535
SERVICE = "robotics-fleet_telemetry_aggregator-9626"
DESCRIPTION = "GTM fleet telemetry aggregator service cycle 9626"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
