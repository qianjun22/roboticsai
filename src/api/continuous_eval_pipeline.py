import datetime,fastapi,uvicorn
PORT=8888
SERVICE="continuous_eval_pipeline"
DESCRIPTION="Continuous eval pipeline — automated nightly SR eval after each DAgger iter"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/pipeline")
def pipeline(): return {"trigger":"on checkpoint saved","eval_protocol":{"episodes":20,"gpu":"GPU0 (dedicated eval)","timeout_min":30},"metrics":["SR","mean_episode_length","mean_cube_z","diverged_steps_pct"],"reporting":["Slack notification","sr_trend_monitor.py update","OCI Monitoring metric push"],"auto_promote":"if SR > prev_best: tag as best_checkpoint","regression_alert":"if SR drops > 10pct: page on-call"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
