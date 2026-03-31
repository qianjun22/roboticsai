import datetime,fastapi,uvicorn
PORT=19316
SERVICE="hour_jun25_lora_code"
DESCRIPTION="Jun 25 3pm: LoRA implementation -- HuggingFace PEFT -- rank 16, alpha 32 -- 4 hours of coding"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
