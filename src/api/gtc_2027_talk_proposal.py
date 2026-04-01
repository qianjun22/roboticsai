import datetime,fastapi,uvicorn
PORT=8846
SERVICE="gtc_2027_talk_proposal"
DESCRIPTION="GTC 2027 talk proposal — OCI Robot Cloud: from sim to real at scale"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/proposal")
def proposal(): return {"title":"OCI Robot Cloud: Scaling Foundation Robot Model Fine-Tuning from Sim to Real","abstract":"We present OCI Robot Cloud, a cloud infrastructure platform for GR00T-based robot learning. Starting from a 5pct baseline, DAgger training on OCI A100 GPUs achieves 100pct simulation SR at $0.43/run, 9.6x cheaper than AWS. We show the complete pipeline: Genesis SDG -> GR00T fine-tune -> DAgger online learning -> real robot deployment.","format":"45-min technical talk + live demo","co_presenter":"NVIDIA GR00T team (TBD)","submission_deadline":"Sept 2026","conference_date":"March 2027"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
