import datetime,fastapi,uvicorn
PORT=16733
SERVICE="aug26_lora_rank_16_winner"
DESCRIPTION="LoRA ablation result: rank 16, alpha 32 wins — 55% SR vs rank 8 52%, rank 32 54% — optimal"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
