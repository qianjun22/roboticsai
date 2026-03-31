import datetime,fastapi,uvicorn
PORT=14719
SERVICE="eng_notes_may_disk_usage"
DESCRIPTION="May 2026 disk: /tmp at 180GB — dataset 50GB + checkpoints 120GB (5 iters × 24GB/iter)"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
