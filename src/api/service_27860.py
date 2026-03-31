import datetime,fastapi,uvicorn
PORT=27860
SERVICE="series_c_summary"
DESCRIPTION="Series C PIPE $300M: Coatue lead, Korea + India offices, TaskML acquisition, H100 cluster, RCLD +12%, Oracle + NVIDIA follow"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
