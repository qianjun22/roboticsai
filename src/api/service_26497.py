import datetime,fastapi,uvicorn
PORT=26497
SERVICE="sp500_obsidian_note"
DESCRIPTION="Obsidian note Jun 2033: 'S&P 500 today. 2026 I was alone. 2033 I am in the index. The algorithm compound.'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
