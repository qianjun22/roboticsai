import datetime,fastapi,uvicorn
PORT=8939
SERVICE="competitive_moat_analysis"
DESCRIPTION="Competitive moat analysis — why OCI Robot Cloud is defensible long-term"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/moats")
def moats(): return {"moat1":{"name":"NVIDIA preferred cloud","strength":"high","time_to_replicate":"3+ years","desc":"Exclusive co-engineering + preferred placement in NVIDIA ecosystem"},"moat2":{"name":"Data flywheel","strength":"high","desc":"Largest pooled robot training dataset (100k+ eps by 2027)"},"moat3":{"name":"Cost leadership","strength":"medium","desc":"OCI A100 9.6x cheaper, but AWS can close gap"},"moat4":{"name":"DAgger expertise","strength":"medium","desc":"Only cloud with DAgger-as-a-service (patentable)"},"moat5":{"name":"Oracle enterprise channel","strength":"high","desc":"Direct path to Fortune 500 manufacturers"}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
