import datetime,fastapi,uvicorn
PORT=22102
SERVICE="spacemouse_why_not_joystick"
DESCRIPTION="Why not joystick: joystick 2D XY -- SpaceMouse 6D XYZ+RPY -- robot arm needs all 6 degrees -- required"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
