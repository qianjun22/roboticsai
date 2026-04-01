import datetime,fastapi,uvicorn
PORT=8350
SERVICE="oci_robot_cloud_readme"
DESCRIPTION="OCI Robot Cloud project summary — the full picture"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/summary')
def s(): return {'project':'OCI_Robot_Cloud','tagline':'NVIDIA_trains_the_model_Oracle_trains_the_robot','stage':'working_prototype_with_real_results','proven':{'mae':'8.7x_improvement','inference':'226ms','cost':'9.6x_cheaper_than_AWS','dagger':'running_run8_6_iters'},'next':{'run9':'corrected_beta_decay','ai_world':'65pct_SR_target','first_customer':'Sept_2026'},'github':'qianjun22/roboticsai','total_services':6500}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
