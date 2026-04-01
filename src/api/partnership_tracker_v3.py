import datetime,fastapi,uvicorn
PORT=8359
SERVICE="partnership_tracker_v3"
DESCRIPTION="Partnership tracker v3 — NVIDIA, OCI, VCs, customers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/partnerships')
def p(): return [{'partner':'NVIDIA','type':'tech_partner','status':'pitching_via_Greg','ask':'preferred_cloud_status'},{'partner':'Oracle_internal','type':'product_sponsor','status':'CEO_pitch_pending','ask':'official_product'},{'partner':'Machina_Labs','type':'design_partner','status':'outreach','ask':'pilot_customer'},{'partner':'a16z','type':'VC','status':'warm_intro','ask':'series_a_lead'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
