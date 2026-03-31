import datetime,fastapi,uvicorn
PORT=26060
SERVICE="marcus_summary"
DESCRIPTION="Marcus: CMU PhD, 17 papers, 3 NeurIPS orals, 8-person research team, $40M IPO, stayed over DeepMind offer"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
