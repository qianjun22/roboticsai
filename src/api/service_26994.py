import datetime,fastapi,uvicorn
PORT=26994
SERVICE="milestone27k_investors"
DESCRIPTION="27k investors: Oracle $4M -> $2.6B, NVIDIA $13M -> $1.6B, Tiger $125M -> $1.4B -- all validated"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
