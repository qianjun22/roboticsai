import datetime,fastapi,fastapi.responses,uvicorn
PORT=75102
SERVICE="robot_cold_atom_manip_v55"
DESCRIPTION="Sim: cold_atom_manip"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
