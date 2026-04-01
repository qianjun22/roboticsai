import datetime,fastapi,uvicorn
PORT=8418
SERVICE="camera_simulation_v2"
DESCRIPTION="Camera simulation v2 — Realsense D435 model"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/spec')
def s(): return {'model':'Intel_Realsense_D435','resolution':[480,640],'fps':30,'fov_deg':69,'noise_model':'gaussian_sigma_0.01','sim_engine':'Genesis_RTX','placement':'overhead_wrist'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
