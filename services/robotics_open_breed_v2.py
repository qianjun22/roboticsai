import datetime, fastapi, fastapi.responses, uvicorn
PORT=21345; SERVICE="robotics_open_breed_v2"; DESCRIPTION="Open breeding robotics GTM for participatory plant and animal improvement"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard(): return f"<html><body style='background:#0f172a;color:#e2e8f0;padding:32px;font-family:system-ui'><h1 style='color:#C74634'>{SERVICE}</h1><p>{DESCRIPTION}</p><p>Port: {PORT}</p></body></html>"
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
