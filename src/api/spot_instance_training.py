import datetime,fastapi,uvicorn
PORT=9023
SERVICE="spot_instance_training"
DESCRIPTION="Spot instance training — preemptible GPU for 80pct cost reduction on starter tier"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"instance":"OCI Preemptible VM A100","cost_reduction":"80pct vs on-demand","preemption_rate":"<5pct typical","checkpoint_freq":500,"auto_resume":"within 10 min on new spot","use_case":"non-urgent fine-tune jobs (starter tier)","not_for":"DAgger data collection (needs consistent GPU)","fine_tune_cost_spot":"$0.086/run (vs $0.43 on-demand)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
