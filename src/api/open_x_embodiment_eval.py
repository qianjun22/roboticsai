import datetime,fastapi,uvicorn
PORT=8544
SERVICE="open_x_embodiment_eval"
DESCRIPTION="Open X-Embodiment evaluation: compare GR00T-OCI vs RT-2 vs pi0 on cross-embodiment tasks"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/eval")
def eval(): return {"models":{"GR00T_OCI_DAgger":{"sr":0.42,"cost_per_run":0.43},"RT2":{"sr":0.55,"cost":"N/A_private"},"pi0":{"sr":0.61,"cost":"N/A_private"}}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
