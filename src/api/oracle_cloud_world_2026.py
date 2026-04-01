import datetime,fastapi,uvicorn
PORT=8576
SERVICE="oracle_cloud_world_2026"
DESCRIPTION="Oracle Cloud World 2026 prep: OCI Robot Cloud demo slot, joint announcement with NVIDIA"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/event")
def event(): return {"conference":"Oracle CloudWorld 2026","date":"2026-09-22","location":"Las Vegas","demo_slot_requested":True,"joint_announcement":"NVIDIA_GR00T_on_OCI"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
