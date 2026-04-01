import datetime
import fastapi
import uvicorn
PORT = 43793
SERVICE = "robotics-sensor-fusion-gateway-8940"
DESCRIPTION = "GTM sensor fusion gateway service cycle 8940"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
