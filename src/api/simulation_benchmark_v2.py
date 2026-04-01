import datetime,fastapi,uvicorn
PORT=8420
SERVICE="simulation_benchmark_v2"
DESCRIPTION="Simulation benchmark v2 — Genesis vs Isaac vs MuJoCo"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/results')
def r(): return [{'sim':'Genesis','episodes_per_hour':200,'setup_min':15,'oci_cost_per_1000_eps':0.43},{'sim':'Isaac_Sim','episodes_per_hour':150,'setup_min':45,'oci_cost_per_1000_eps':0.57},{'sim':'MuJoCo','episodes_per_hour':500,'setup_min':5,'oci_cost_per_1000_eps':0.17,'limitation':'no_photorealistic_rendering'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
