import datetime,fastapi,uvicorn
PORT=8269
SERVICE="series_a_tracker"
DESCRIPTION="Series A fundraise tracker — target M at M pre"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/status')
def status(): return {'target_raise':8000000,'pre_money_valuation':30000000,'lead_investors':['a16z','Khosla','GV'],'use_of_funds':{'gpu_infra':'40%','team':'40%','sales':'20%'},'timeline':'Q1_2027','status':'warm_outreach'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
