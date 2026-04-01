import datetime,fastapi,uvicorn
PORT=8883
SERVICE="customer_success_playbook"
DESCRIPTION="Customer success playbook — onboarding + retention for OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/playbook")
def playbook(): return {"onboarding":{"day1":"Oracle account + OCI tenancy setup","day3":"Genesis env kickoff call","week2":"first fine-tune run complete","week4":"DAgger pilot results reviewed"},"kpis_tracked":["SR improvement vs baseline","cost_per_run","inference_latency","time_to_first_success"],"qbr":"quarterly business review at 90 days","expansion_signals":["3+ runs/month","additional task requests","team expansion"],"churn_risk_signals":["no runs in 2 weeks","SR not improving after iter3"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
