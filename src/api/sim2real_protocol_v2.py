import datetime,fastapi,uvicorn
PORT=8429
SERVICE="sim2real_protocol_v2"
DESCRIPTION="Sim-to-real transfer protocol v2"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/protocol')
def p(): return {'phase1':'sim_only_65pct_sr_target','phase2':'sim_finetuned_real_eval','phase3':'real_robot_dagger','partner':'Machina_Labs_or_Apptronik','timeline':'Q3_2026_if_partnership_signed','gap_mitigation':['domain_rand','real_images_in_training','dynamics_randomization']}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
