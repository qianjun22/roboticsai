import datetime,fastapi,uvicorn
PORT=20584
SERVICE="run16_n2_finetune"
DESCRIPTION="Run16 N2 fine-tune: 5000 steps, 52min on 2xH100 -- loss 0.089 -- lower than N1.6 0.099"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
