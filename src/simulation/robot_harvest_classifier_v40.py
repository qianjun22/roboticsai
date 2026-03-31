import datetime, fastapi, fastapi.responses, uvicorn
PORT=48702
SERVICE="robot_harvest_classifier_v40"
DESCRIPTION="Simulation: harvest_classifier"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/",response_class=fastapi.responses.HTMLResponse)
def dashboard():
    return f"<html><body style='background:#0f172a;color:#e2e8f0;font-family:system-ui'><div style='background:#C74634;padding:20px'><h1 style='color:white;margin:0'>robot_harvest_classifier_v40</h1></div><div style='padding:20px'><p>Port: 48702</p><p>Status: operational</p></div></body></html>"
if __name__=="__main__":
    uvicorn.run(app,host="0.0.0.0",port=PORT)
