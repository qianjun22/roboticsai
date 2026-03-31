import datetime,fastapi,uvicorn
PORT=18475
SERVICE="s2r_gap_by_task"
DESCRIPTION="Gap by task: pick-cube (10pp) < palletize (15pp) < pour (20pp) < deformable (35pp) — complexity scales gap"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
