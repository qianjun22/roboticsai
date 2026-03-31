import datetime,fastapi,uvicorn
PORT=23571
SERVICE="papers_2027_ml_eng_authors"
DESCRIPTION="Author split: Jun (company story + leadership), ML Eng 1 (LoRA experiments), ML Eng 2 (mixed DAgger)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
