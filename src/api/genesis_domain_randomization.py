import datetime,fastapi,uvicorn
PORT=8875
SERVICE="genesis_domain_randomization"
DESCRIPTION="Genesis domain randomization — sim-to-real gap reduction via varied sim conditions"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"randomization_params":{"lighting":{"intensity":[0.5,2.0],"direction":"random hemisphere"},"cube_texture":{"options":["wood","metal","plastic","rubber"]},"cube_mass_kg":{"range":[0.1,0.5]},"gripper_friction":{"range":[0.5,1.5]},"camera_noise":{"gaussian_std":0.02,"salt_pepper":0.001},"table_texture":{"options":["white","dark","wood"]}},"demos_per_randomization":50,"expected_sim_to_real_improvement":"40pct better real SR vs no DR"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
