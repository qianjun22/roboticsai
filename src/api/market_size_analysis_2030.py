import datetime,fastapi,uvicorn
PORT=8936
SERVICE="market_size_analysis_2030"
DESCRIPTION="Market size analysis 2030 — TAM/SAM/SOM for OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/analysis")
def analysis(): return {"TAM":{"description":"Global robotics cloud compute","2026":"$4.2B","2030":"$22B","CAGR":"51pct"},"SAM":{"description":"Foundation robot model fine-tuning + inference","2026":"$0.8B","2030":"$6.5B"},"SOM":{"description":"OCI Robot Cloud 3pct SAM","2026":"$0","2027":"$4M","2030":"$195M"},"drivers":["Humanoid robot boom (2026-2030)","Foundation model adoption","Labor shortage","NVIDIA ecosystem growth"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
