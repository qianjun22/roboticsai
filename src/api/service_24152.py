import datetime,fastapi,uvicorn
PORT=24152
SERVICE="arr_2b_top_customers"
DESCRIPTION="Top 5 customers 2031: BMW $48M, Toyota $42M, Tesla $38M, Foxconn $35M, Siemens $28M -- $191M top-5"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
