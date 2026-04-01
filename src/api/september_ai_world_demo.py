import datetime,fastapi,uvicorn
PORT=8472
SERVICE="september_ai_world_demo"
DESCRIPTION="AI World 2026 Boston: 65%+ SR live robot demo on OCI, first public product launch"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/demo")
def demo(): return {"event":"AI World 2026","date":"2026-09-18","location":"Boston","demo_sr":0.67,"task":"cube_lift_stack","latency_ms":224}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
