import datetime,fastapi,uvicorn
PORT=8401
SERVICE="run8_eval_planner"
DESCRIPTION="DAgger run8 eval planner — after iter6 complete"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/plan')
def p(): return {'checkpoint_to_eval':'iter_06/checkpoint-5000','episodes':20,'seed':42,'expected_sr':'5-15%','compare_against':'BC_baseline_5%','eval_script':'python3 src/eval/closed_loop_eval.py --checkpoint /tmp/dagger_run8/checkpoints/iter_06/checkpoint-5000 --episodes 20'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
