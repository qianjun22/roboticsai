import datetime,fastapi,uvicorn
PORT=8165
SERVICE="gtc_talk_abstract_v2"
DESCRIPTION="GTC 2027 talk abstract v2: updated with DAgger run8 results"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
