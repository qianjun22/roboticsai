import datetime,fastapi,uvicorn
PORT=8204
SERVICE="foundation_model_eval"
DESCRIPTION="Foundation model eval: GR00T N1.6 vs RDT-1B vs Pi0 benchmark"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
