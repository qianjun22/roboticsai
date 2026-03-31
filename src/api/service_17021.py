import datetime,fastapi,uvicorn
PORT=17021
SERVICE="jun26_wrist_cam_order"
DESCRIPTION="Jun 2026 wrist cam: RealSense D435 ordered ($200) — arrived Jun 8 — mount designed in Fusion 360"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
