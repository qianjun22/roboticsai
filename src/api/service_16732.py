import datetime,fastapi,uvicorn
PORT=16732
SERVICE="aug26_lora_design_v2"
DESCRIPTION="Aug 2026 LoRA design v2: ablation planned (rank 4/8/16/32) × (alpha 16/32/64) — 12 conditions"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
