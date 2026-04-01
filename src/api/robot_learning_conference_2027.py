import datetime,fastapi,uvicorn
PORT=9015
SERVICE="robot_learning_conference_2027"
DESCRIPTION="Robot Learning Conference 2027 — OCI Robot Cloud submissions and presence"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"conference":"CoRL 2027","submissions":[{"title":"Cloud-Scale DAgger: 100pct SR at $0.43","status":"submitted (from CoRL 2026 work)"},{"title":"Sim-to-Real Transfer via Mixed DAgger","status":"new submission"}],"booth":"OCI sponsor booth","demo":"live run9 fine-tuning on OCI","networking":"meet NVIDIA robotics team + partner labs","target_leads":20}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
