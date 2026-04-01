import datetime,fastapi,uvicorn
PORT=8887
SERVICE="sept_2026_ai_world_debrief"
DESCRIPTION="AI World 2026 debrief plan — post-event follow-up and lead conversion"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"event":"AI World 2026","date":"September 2026","debrief_actions":[{"day":"D+1","action":"LinkedIn post with demo video"},{"day":"D+3","action":"Follow up with all booth visitors"},{"day":"D+7","action":"Pilot proposal sent to top 5 prospects"},{"day":"D+14","action":"NVIDIA co-announcement blog post"},{"day":"D+30","action":"First pilot complete, case study published"}],"kpis":["leads_captured","pilots_proposed","contracts_signed","press_pickups"],"target":"2 paid contracts within 30 days post-event"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
