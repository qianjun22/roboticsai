import datetime
import fastapi
import uvicorn
PORT = 43796
SERVICE = "dagger-run8559-planner"
DESCRIPTION = "DAgger run 8559 planning service cycle 8941"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
