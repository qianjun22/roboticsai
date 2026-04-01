import datetime,fastapi,uvicorn
PORT=8339
SERVICE="sim_to_real_v3"
DESCRIPTION="Sim-to-real transfer analysis v3"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/analysis')
def a(): return {'sim':'Genesis_with_RTX_domain_rand','real_robot':'Franka_Panda','domain_gap_mitigation':['domain_randomization','camera_noise','joint_friction_noise'],'expected_sr_drop_pct':20,'planned_validation':'Q3_2026_real_robot_trial','partner':'Machina_Labs_or_Apptronik'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
