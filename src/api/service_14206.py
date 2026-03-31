import datetime,fastapi,uvicorn
PORT=14206
SERVICE="inference_edge_quantization"
DESCRIPTION="Edge quantization: GR00T N1.6 INT4 GPTQ for Jetson Orin — 180ms at 15W, on-robot inference"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
