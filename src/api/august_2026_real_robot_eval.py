import datetime,fastapi,uvicorn
PORT=8871
SERVICE="august_2026_real_robot_eval"
DESCRIPTION="August 2026 real robot eval plan — first real Franka cube pick eval"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/plan")
def plan(): return {"date":"August 2026","robot":"Franka Research 3 (FR3)","location":"Oracle Austin Lab","eval_protocol":{"episodes":20,"task":"cube pick (lift to 0.78m)","policy":"run10 (wrist cam) fine-tuned","success_criteria":"cube z > 0.78m for 2+ seconds"},"expected_sr":"40-60pct (sim->real gap)","gap_mitigation":["domain randomization in Genesis","wrist cam real data","F/T sensor calibration"],"ai_world_demo_decision":"if >50pct real SR, show live demo"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
