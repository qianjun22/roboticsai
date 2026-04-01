import datetime,fastapi,uvicorn
PORT=8577
SERVICE="robot_leaderboard_v2"
DESCRIPTION="LIBERO robot manipulation leaderboard v2: OCI DAgger tracked against academic SOTA"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/leaderboard")
def leaderboard(): return {"task":"LIBERO_Spatial_10","rankings":[{"model":"pi0","sr":0.61},{"model":"ACT","sr":0.61},{"model":"Diffusion_Policy","sr":0.58},{"model":"OCI_DAgger_run12","sr":0.52},{"model":"BC_1000","sr":0.05}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
