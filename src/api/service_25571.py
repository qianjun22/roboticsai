import datetime,fastapi,uvicorn
PORT=25571
SERVICE="spacemouse_bimanual"
DESCRIPTION="Bimanual SpaceMouse: 2 SpaceMouses for bimanual correction -- 2-person team or 1 with both hands -- options"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
