import datetime, fastapi, fastapi.responses, uvicorn
PORT=45651
SERVICE="robotics_icp_builder_v37"
DESCRIPTION="GTM: icp_builder"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard():
    return f"<html><body style='background:#0f172a;color:#e2e8f0;font-family:system-ui'><div style='background:#C74634;padding:20px'><h1 style='color:white;margin:0'>robotics_icp_builder_v37</h1></div><div style='padding:20px'><p>Port: 45651</p><p>Status: operational</p></div></body></html>"
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=PORT)
