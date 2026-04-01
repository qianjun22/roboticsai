import datetime,fastapi,uvicorn
PORT=9011
SERVICE="q1_2027_business_review"
DESCRIPTION="Q1 2027 business review — Series A closed, GTC, 5 customers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/review")
def review(): return {"quarter":"Q1 2027","achievements":["Series A $12M closed (NVIDIA Ventures)","GTC 2027: 1200 attendees, 150 leads","5 paying customers, $150k MRR","Run17: 81pct real SR","NVIDIA N2 preview access"],"missed":["APAC launch slipped to Q2"],"highlight":"GTC drove 6x leads in single quarter","key_metric":"$150k MRR = $1.8M ARR run-rate"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
