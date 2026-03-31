import datetime,fastapi,uvicorn
PORT=26477
SERVICE="home_robot_jun_home"
DESCRIPTION="Jun home robot: Jun uses Figure 02 at home -- does dishes -- Jul Obsidian: 'It folded my shirts wrong. I corrected it. It learned.'"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
