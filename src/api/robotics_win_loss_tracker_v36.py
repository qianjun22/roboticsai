import datetime, fastapi, fastapi.responses, uvicorn
PORT=44207
SERVICE="robotics_win_loss_tracker_v36"
DESCRIPTION="GTM: win_loss_tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard():
    return f"<html><body style='background:#0f172a;color:#e2e8f0;font-family:system-ui'><div style='background:#C74634;padding:20px'><h1 style='color:white;margin:0'>robotics_win_loss_tracker_v36</h1></div><div style='padding:20px'><p>Port: 44207</p><p>Status: operational</p></div></body></html>"
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=PORT)
