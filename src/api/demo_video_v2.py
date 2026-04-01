import datetime,fastapi,uvicorn
PORT=8384
SERVICE="demo_video_v2"
DESCRIPTION="Demo video v2 planner — AI World demo script"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/script')
def s(): return {'opening':'GR00T_N1.6_zero_shot_5_SR','act1':'8.7x_MAE_with_IK_SDG','act2':'DAgger_run1_results_vs_BC','act3':'live_inference_226ms','closing':'path_to_65_SR_AI_World','length_min':3,'format':'side_by_side_sim_and_latency'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
