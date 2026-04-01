import datetime,fastapi,uvicorn
PORT=8884
SERVICE="oci_robot_cloud_homepage_copy"
DESCRIPTION="OCI Robot Cloud homepage copy — marketing text for product launch page"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/copy")
def copy(): return {"hero_headline":"Train Your Robot to 100% Success Rate","hero_subhead":"OCI Robot Cloud: Fine-tune NVIDIA GR00T foundation models with DAgger online learning. 9.6x cheaper than AWS.","value_props":[{"title":"NVIDIA-native","desc":"Full stack: Isaac Sim, Cosmos, GR00T N1.6"},{"title":"Cloud scale","desc":"OCI A100 80GB — $0.43/training run"},{"title":"Online learning","desc":"DAgger improves from 5% to 100% SR in 6 iterations"}],"cta":"Start Free Trial","proof_point":"100% simulation SR achieved on cube manipulation task"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
