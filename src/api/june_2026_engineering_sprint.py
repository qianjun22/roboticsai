import datetime,fastapi,uvicorn
PORT=8864
SERVICE="june_2026_engineering_sprint"
DESCRIPTION="June 2026 engineering sprint — wrist camera + LoRA + real robot setup"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/sprint")
def sprint(): return {"month":"June 2026","theme":"Hardware Integration + Efficiency","items":[{"task":"Run10: wrist camera integration","priority":"P0"},{"task":"Run11: LoRA adapters","priority":"P0"},{"task":"Real Franka setup at oracle lab","priority":"P1"},{"task":"NVIDIA meeting done","priority":"P1"},{"task":"Design partner #2 signed","priority":"P2"},{"task":"CoRL paper submitted","priority":"P2"},{"task":"Public beta landing page live","priority":"P2"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
