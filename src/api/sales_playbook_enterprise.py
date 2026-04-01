import datetime,fastapi,uvicorn
PORT=9022
SERVICE="sales_playbook_enterprise"
DESCRIPTION="Enterprise sales playbook — $50k+ deals via Oracle enterprise channel"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/playbook")
def playbook(): return {"stages":[{"stage":"Discovery","questions":["What robot? What task?","Current training cost?","Success rate target?"],"duration":"1 call"},{"stage":"Technical Eval","actions":["Genesis env setup","Baseline fine-tune","Share run8 benchmark"],"duration":"2 weeks"},{"stage":"Business Case","actions":["ROI calculator","Cost comparison vs AWS","Reference customer intro"],"duration":"1 week"},{"stage":"Close","actions":["MSA + SOW","Oracle procurement"],"duration":"2-4 weeks"}],"avg_deal_size":"$30k/month","avg_sales_cycle":"6 weeks"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
