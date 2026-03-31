import datetime,fastapi,uvicorn
PORT=21893
SERVICE="neurips_deepmind_convo"
DESCRIPTION="DeepMind researcher: 'we tried sim-to-real mixing and it didn't work' -- Jun: 'ratio matters, 70:30 is key'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
