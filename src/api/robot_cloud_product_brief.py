import datetime,fastapi,uvicorn
PORT=8299
SERVICE="robot_cloud_product_brief"
DESCRIPTION="OCI Robot Cloud one-page product brief"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/brief')
def b(): return {'product':'OCI Robot Cloud','tagline':'NVIDIA trains the model. Oracle trains the robot.','value_props':['9.6x_cheaper_than_AWS','226ms_inference','GR00T_N1.6_fine_tuning','US_origin_data','OCI_A100_80GB'],'target_customers':'Robotics_startups_with_GR00T_need','pricing_monthly':4500}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
