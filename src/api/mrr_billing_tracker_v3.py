import datetime,fastapi,fastapi.responses,uvicorn
PORT=8106
SERVICE="mrr_billing_tracker_v3"
DESCRIPTION="MRR Billing Tracker v3 - Real-time revenue tracking"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
import datetime
CUSTOMERS=[
    {"name":"Machina Labs","plan":"starter","mrr":4999,"since":"2026-07-01","status":"active"},
    {"name":"Apptronik","plan":"growth","mrr":0,"since":None,"status":"pilot"},
]
@app.get("/mrr")
def mrr():
    active=[c for c in CUSTOMERS if c["status"]=="active"]
    return {"total_mrr":sum(c["mrr"] for c in active),"arr":sum(c["mrr"] for c in active)*12,"customers":len(active)}
@app.get("/customers")
def customers(): return CUSTOMERS

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
