import datetime, fastapi, fastapi.responses, uvicorn
PORT=21314; SERVICE="robot_magnetoponic"; DESCRIPTION="Magnetoponic robotics simulation with magnetic field plant growth enhancement"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard(): return f"<html><body style='background:#0f172a;color:#e2e8f0;padding:32px;font-family:system-ui'><div style='background:#C74634;padding:20px;border-radius:8px;margin-bottom:20px'><h1 style='margin:0;color:#fff'>{SERVICE}</h1><p style='color:#fca5a5;margin:4px 0 0'>{DESCRIPTION}</p></div><p>Port: {PORT} | Status: <span style='color:#4ade80'>Live</span></p></body></html>"
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
