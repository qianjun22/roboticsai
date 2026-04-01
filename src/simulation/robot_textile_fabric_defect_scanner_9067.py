import datetime
import fastapi
import uvicorn
PORT = 44298
SERVICE = "robot-textile-fabric_defect_scanner-9067"
DESCRIPTION = "Textile simulation cycle 9067"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
