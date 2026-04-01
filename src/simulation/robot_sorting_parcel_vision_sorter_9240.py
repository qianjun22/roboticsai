import datetime
import fastapi
import uvicorn
PORT = 44990
SERVICE = "robot-sorting-parcel_vision_sorter-9240"
DESCRIPTION = "Sorting simulation cycle 9240"
app = fastapi.FastAPI(title=SERVICE, version="1.0.0", description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE, "port": PORT, "ts": datetime.datetime.utcnow().isoformat()}
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
