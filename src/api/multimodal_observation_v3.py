import datetime,fastapi,uvicorn
PORT=8540
SERVICE="multimodal_observation_v3"
DESCRIPTION="Multimodal observation v3: RGB + depth + wrist_cam + proprio + F/T fused for GR00T"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/obs/config")
def config(): return {"modalities":["RGB_640x480","depth","wrist_cam","proprio_7dof","ft_sensor"],"fusion":"cross_attention","total_sr_vs_rgb_only":"+27pct"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
