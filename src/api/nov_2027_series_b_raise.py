import datetime,fastapi,uvicorn
PORT=9028
SERVICE="nov_2027_series_b_raise"
DESCRIPTION="November 2027 Series B raise — $40M at $200M pre-money"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/round")
def round(): return {"date":"November 2027","amount":"$40M","valuation":"$200M pre-money","lead":"Tiger Global","participants":["NVIDIA Ventures (follow-on)","OCI (follow-on)","Playground Global"],"metrics_at_close":{"arr":"$9.6M","customers":35,"nrr":"138pct","real_sr":"91pct (GR00T N2)"},"use_of_funds":{"engineering":"40pct","sales":"35pct","infra":"25pct"},"hires":"20 additional (total 30 team)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
