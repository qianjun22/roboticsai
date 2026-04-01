import datetime,fastapi,uvicorn
PORT=8591
SERVICE="q2_2027_roadmap_tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/roadmap")
def roadmap(): return {"quarter":"Q2-2027","milestones":[
  {"name":"GTC 2027 talk","date":"2027-03-18","status":"planned","owner":"Jun"},
  {"name":"3 paying customers","date":"2027-03-31","target_arr":"$500k"},
  {"name":"NVIDIA co-engineering agreement","date":"2027-04-30"},
  {"name":"Series A close","date":"2027-06-30","target":"$12M"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
