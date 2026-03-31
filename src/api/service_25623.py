import datetime,fastapi,uvicorn
PORT=25623
SERVICE="tools_obsidian_daily"
DESCRIPTION="Daily note: Jun writes 200-word daily note every morning -- 5am -- 8yr x 365 = 2920 daily notes by 2034"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
