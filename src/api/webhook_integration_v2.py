import datetime,fastapi,uvicorn
PORT=8314
SERVICE="webhook_integration_v2"
DESCRIPTION="Webhook integration v2 — training events + alerts"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/events')
def e(): return ['training.started','training.checkpoint_saved','training.completed','eval.started','eval.completed','eval.sr_improved','billing.invoice_generated','system.maintenance']
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
