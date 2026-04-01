import datetime, fastapi, fastapi.responses, uvicorn
PORT=47980
SERVICE="dagger_run9605_planner"
DESCRIPTION="DAgger run 9605"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard():
    return f"<html><body style='background:#0f172a;color:#e2e8f0;font-family:system-ui'><div style='background:#C74634;padding:20px'><h1 style='color:white;margin:0'>dagger_run9605_planner</h1></div><div style='padding:20px'><p>Port: 47980</p><p>Status: operational</p></div></body></html>"
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=PORT)
