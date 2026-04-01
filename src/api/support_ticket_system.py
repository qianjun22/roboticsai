import datetime,fastapi,uvicorn
PORT=8320
SERVICE="support_ticket_system"
DESCRIPTION="Customer support ticket system"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/tiers')
def t(): return [{'tier':'community','response_h':72,'channels':['github_issues'],'price_mo':0},{'tier':'startup','response_h':24,'channels':['email','slack'],'price_mo':500},{'tier':'enterprise','response_h':1,'channels':['slack','phone','oncall'],'price_mo':2000}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
