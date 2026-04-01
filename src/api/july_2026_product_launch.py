import datetime,fastapi,uvicorn
PORT=8849
SERVICE="july_2026_product_launch"
DESCRIPTION="July 2026 product launch — OCI Robot Cloud public beta"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/launch")
def launch(): return {"date":"July 2026","name":"OCI Robot Cloud Public Beta","url":"roboticscloud.oracle.com","features_at_launch":["Genesis SDG (1k-10k demo generation)","GR00T N1.6 fine-tuning (1000-10000 steps)","DAgger online learning (up to 6 iters)","Inference API (JSON/gRPC)","Usage dashboard","OCI Free Trial compatible"],"marketing":["Oracle blog post","NVIDIA partner announcement","LinkedIn launch post","HN Show HN"],"goal":"100 signups in first 30 days"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
