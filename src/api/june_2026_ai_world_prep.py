import datetime,fastapi,uvicorn
PORT=8840
SERVICE="june_2026_ai_world_prep"
DESCRIPTION="AI World 2026 prep — June build-up for September demo launch"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/prep")
def prep(): return {"event":"AI World 2026","date":"September 2026","june_tasks":["Design partner pilot live (1 startup)","NVIDIA meeting done","Run9 eval complete","Multi-seed validation done","Real Franka setup procured","Sim-to-real gap analysis published"],"demo_goals":["Live DAgger training demo on OCI GPU","100pct SR result presented","Design partner case study","OCI pricing calculator live"],"booth_ask":"NVIDIA co-booth or adjacent placement"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
