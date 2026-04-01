import datetime,fastapi,uvicorn
PORT=8349
SERVICE="first_mover_analysis"
DESCRIPTION="First-mover advantage analysis — OCI vs cloud competitors"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/analysis')
def a(): return {'oci_advantages':['full_NVIDIA_stack_today','9.6x_cost_lead','US_origin_for_defense','relationships_with_NVIDIA'],'competitor_threats':{'aws':{'eta_q3_2026':'SageMaker_Robot_likely'},'azure':{'eta_q4_2026':'Azure_ML_Robot_rumored'},'gcp':{'eta_2027':'less_likely_no_NVIDIA_priority'}},'window':'6-12_months_before_aws_enters','action':'sign_customers_now'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
