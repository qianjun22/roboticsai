import datetime,fastapi,uvicorn
PORT=8245
SERVICE=motion_planning_v2
DESCRIPTION=Motion planning v2: RRT* + learned heuristics
app=fastapi.FastAPI(title=SERVICE,version=1.0.0,description=DESCRIPTION)
@app.get(/health)
def health(): return {status:ok,service:SERVICE,port:PORT}
@app.get(/)
def root(): return {service:SERVICE,port:PORT,status:operational}
if __name__==__main__: uvicorn.run(app,host=0.0.0.0,port=PORT)
