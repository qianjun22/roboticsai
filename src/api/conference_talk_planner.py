import datetime,fastapi,uvicorn
PORT=8385
SERVICE="conference_talk_planner"
DESCRIPTION="Conference talk pipeline — GTC + ICRA + CoRL"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/talks')
def t(): return [{'conf':'GTC_2027','status':'abstract_ready','deadline':'2026-10-15','format':'40min_talk+demo'},{'conf':'CoRL_2026','status':'paper_in_progress','deadline':'2026-06-01','format':'paper+poster'},{'conf':'ICRA_2027','status':'planned','deadline':'2026-09-15','format':'paper+demo'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
