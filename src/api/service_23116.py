import datetime,fastapi,uvicorn
PORT=23116
SERVICE="run_arc_summary"
DESCRIPTION="Run arc: 5% (BC) -> 35% (run8 DAgger) -> 48% (run9 cam) -> 55% (run10 LoRA) -> 70% (run14) -> 90% (run18)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
