import datetime,fastapi,uvicorn
PORT=8607
SERVICE="dagger_curriculum_scheduler"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/schedule")
def schedule(): return {"curriculum":[
  {"phase":1,"task":"cube_lift","difficulty":"easy","cube_z_range":[0.45,0.55],"target_sr":0.65},
  {"phase":2,"task":"cube_lift","difficulty":"medium","cube_z_range":[0.40,0.60],"target_sr":0.55},
  {"phase":3,"task":"cube_place","difficulty":"easy","target_sr":0.45},
  {"phase":4,"task":"cube_place","difficulty":"hard","target_sr":0.35}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
