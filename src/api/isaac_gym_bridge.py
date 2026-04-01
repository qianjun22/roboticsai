import datetime,fastapi,uvicorn
PORT=8412
SERVICE="isaac_gym_bridge"
DESCRIPTION="Isaac Gym/Sim bridge — environment wrappers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/envs')
def e(): return ['FrankaCubeStack','FrankaPegInHole','FrankaPickAndPlace','HumanoidStand','ShadowHandManipulate']
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
