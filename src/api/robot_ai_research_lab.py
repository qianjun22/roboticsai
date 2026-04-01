import datetime,fastapi,uvicorn
PORT=8579
SERVICE="robot_ai_research_lab"
DESCRIPTION="OCI Robot AI Lab: internal research on DAgger variants, world models, contact-rich manipulation"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/lab/projects")
def projects(): return {"active_projects":["DAgger_variance_reduction","world_model_planning","contact_rich_policy","multi_embodiment_transfer"],"papers_in_prep":2,"gpu_hours_used_ytd":14400}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
