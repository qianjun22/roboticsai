import datetime,fastapi,uvicorn
PORT=8569
SERVICE="robot_training_cost_calculator"
DESCRIPTION="Training cost calculator: input demos+steps, get OCI vs AWS vs on-prem cost comparison"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/calculate")
def calculate(demos:int=1000,steps:int=5000): return {"demos":demos,"steps":steps,"oci_usd":round(demos*steps*0.0000043/100,2),"aws_usd":round(demos*steps*0.0000412/100,2),"onprem_usd":round(demos*steps*0.0000180/100,2),"oci_savings_vs_aws_x":9.6}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
