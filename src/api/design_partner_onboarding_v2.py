import datetime,fastapi,uvicorn
PORT=8262
SERVICE="design_partner_onboarding_v2"
DESCRIPTION="Design partner onboarding tracker v2 — June 2026"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/partners')
def partners(): return [{'name':'Machina Labs','status':'pilot_active','monthly_value':3000,'use_case':'sheet_metal_forming'},{'name':'Apptronik','status':'evaluating','monthly_value':4500,'use_case':'humanoid_manipulation'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
