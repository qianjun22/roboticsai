import datetime,fastapi,uvicorn
PORT=8494
SERVICE="manipulation_curriculum_v3"
DESCRIPTION="Manipulation curriculum v3: progressive tasks from reach to grasp to lift to place"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/curriculum")
def curriculum(): return {"stages":["reach","grasp","lift","place"],"stage_sr":[0.91,0.78,0.42,0.0],"current":"lift","auto_advance":True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
