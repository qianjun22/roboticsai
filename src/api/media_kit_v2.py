import datetime,fastapi,uvicorn
PORT=8389
SERVICE="media_kit_v2"
DESCRIPTION="Press media kit v2 — logos, screenshots, boilerplate"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/kit')
def k(): return {'company':'OCI Robot Cloud by Oracle','founded':'2026-Q1','one_liner':'The first cloud designed for NVIDIA robot foundation model fine-tuning','key_facts':['9.6x cheaper than AWS','226ms inference','8.7x MAE improvement','OCI A100 80GB GPU'],'logo_url':'/static/logo.png'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
