import datetime,fastapi,uvicorn
PORT=8409
SERVICE="robot_cloud_website_v2"
DESCRIPTION="Robot Cloud website v2 content planner"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/pages')
def p(): return [{'page':'home','headline':'Train Your Robot in the Cloud','cta':'Start Free Trial'},{'page':'pricing','tiers':3,'starting_at':1500},{'page':'docs','sections':8},{'page':'blog','posts':4},{'page':'case-studies','count':0,'target_count_by_ai_world':2}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
