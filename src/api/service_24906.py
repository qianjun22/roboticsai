import datetime,fastapi,uvicorn
PORT=24906
SERVICE="groot_origin_lora_insight"
DESCRIPTION="LoRA insight: GR00T weights too large for full fine-tune on OCI A100 -- LoRA solves it -- 3B to 14M params"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
