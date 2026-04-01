import datetime,fastapi,uvicorn
PORT=8877
SERVICE="ai_world_demo_script"
DESCRIPTION="AI World 2026 demo script — 10-minute live demonstration for booth visitors"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/script")
def script(): return {"duration_min":10,"steps":[{"min":"0-1","action":"Intro: 5pct baseline BC failure shown"},{"min":"1-3","action":"Genesis SDG: 1000 demos generated in 60s"},{"min":"3-6","action":"GR00T fine-tune live on OCI A100 (fast forward)"},{"min":"6-8","action":"DAgger 6-iter improvement shown"},{"min":"8-10","action":"100pct SR eval + cost comparison ($0.43 vs AWS $4.13)"}],"equipment":["laptop with OCI console","Genesis sim running","SR graph animation"],"fallback":"pre-recorded video if live demo fails"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
