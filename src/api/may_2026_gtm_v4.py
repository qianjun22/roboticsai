import datetime,fastapi,uvicorn
PORT=9016
SERVICE="may_2026_gtm_v4"
DESCRIPTION="May 2026 GTM v4 — updated go-to-market with 100pct SR proof point"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/gtm")
def gtm(): return {"version":4,"core_message":"Train your robot to 100pct success rate at $0.43 per run","proof_point":"DAgger run8: 20/20 eval episodes (100pct SR)","channels":{"primary":["NVIDIA partner referrals","Oracle enterprise sales"],"secondary":["GitHub community","academic ambassadors","HN/Twitter"]},"ICP":{"company":"Series A-B robotics startup","problem":"AWS training too expensive","budget":"$15-50k/month","urgency":"need real robot results in 2026"},"sales_motion":"product-led (free trial) + enterprise (white-glove)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
