import datetime,fastapi,uvicorn
PORT=8552
SERVICE="competitive_moat_analysis"
DESCRIPTION="Competitive moat: data flywheel, NVIDIA exclusivity, OCI cost advantage, DAgger IP"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/moat")
def moat(): return {"advantages":["NVIDIA_full_stack_only_on_OCI","DAgger_IP_trade_secret","data_flywheel_compounding","9.6x_cost_advantage","GR00T_N2_beta_access"],"durability":"3-5_years"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
