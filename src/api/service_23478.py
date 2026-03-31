import datetime,fastapi,uvicorn
PORT=23478
SERVICE="sales_motion_2027_team"
DESCRIPTION="2027 sales team: VP Sales + 3 AEs + 2 SDRs -- small and efficient -- $18M ARR / 6 people = $3M each"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
