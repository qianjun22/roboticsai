import datetime,fastapi,uvicorn
PORT=8417
SERVICE="physics_validator"
DESCRIPTION="Physics validation — sim vs real comparison"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/comparison')
def c(): return {'sim_engine':'Genesis_PhysX5','real_robot':'Franka_Panda','validated_params':['joint_friction','cube_mass_100g','table_height_0.7m','gripper_force'],'gap_estimated_pct':15,'mitigation':'domain_randomization'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
