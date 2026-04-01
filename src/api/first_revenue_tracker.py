import datetime,fastapi,uvicorn
PORT=8257
SERVICE="first_revenue_tracker"
DESCRIPTION="Track path to first paying customer by Sept 2026"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/pipeline')
def pipeline(): return {'target_date':'2026-09-30','pilot_price_per_month':4500,'design_partners':['machina_labs','apptronik'],'status':'pilot_outreach'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
