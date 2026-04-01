import datetime,fastapi,uvicorn
PORT=8863
SERVICE="oracle_internal_champion_brief"
DESCRIPTION="Oracle internal champion brief — Greg Pavlik + Clay Magouyrk update memo"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/brief")
def brief(): return {"to":["Greg Pavlik (OCI EVP)","Clay Magouyrk (OCI CTO)"],"from_":"Jun Qian","date":"April 2026","headline":"100pct simulation SR achieved; ready for NVIDIA partnership meeting","key_facts":["DAgger run8: 20/20 eval (100pct SR) at 229ms","$0.43/run, 9.6x cheaper than AWS","CEO pitch deck ready","Run9 running to confirm robustness"],"asks":["NVIDIA Isaac/GR00T team intro (Greg direct contact)","Official OCI product license","$0 additional budget needed"],"ceo_pitch":"OCI_Robot_Cloud_CEO_Pitch.pptx"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
