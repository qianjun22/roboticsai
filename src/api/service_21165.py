import datetime,fastapi,uvicorn
PORT=21165
SERVICE="deploy_arch_jetson_tradeoffs"
DESCRIPTION="Jetson tradeoffs: 45ms latency vs 226ms cloud -- smaller model (N1.6 only) -- no N2/N3 on edge yet"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
