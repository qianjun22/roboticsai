import datetime,fastapi,uvicorn
PORT=17274
SERVICE="groot_vs_openVLA"
DESCRIPTION="GR00T vs OpenVLA: OpenVLA 7B open-source, 72% LIBERO sim — GR00T N2 89% — 17pp advantage"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
