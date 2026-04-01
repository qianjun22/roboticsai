import datetime,fastapi,uvicorn
PORT=8381
SERVICE="blog_content_planner"
DESCRIPTION="Blog content planner — technical + thought leadership"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/calendar')
def c(): return [{'title':'8.7x MAE improvement with IK-planned SDG','date':'2026-04-15','type':'technical'},{'title':'Why OCI beats AWS for robot AI training','date':'2026-05-01','type':'competitive'},{'title':'DAgger in production: lessons from run 1-8','date':'2026-06-01','type':'engineering'},{'title':'Path to 65% closed-loop SR','date':'2026-09-01','type':'results'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
