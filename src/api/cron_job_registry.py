import datetime,fastapi,uvicorn
PORT=8410
SERVICE="cron_job_registry"
DESCRIPTION="Cron job registry — automated OCI Robot Cloud tasks"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/jobs')
def j(): return [{'job':'nightly_eval','schedule':'0_2_*_*_*','action':'eval_best_checkpoint_5_eps','status':'active'},{'job':'wave_build_monitor','schedule':'*/30_*_*_*_*','action':'check_wave_progress_log','status':'active'},{'job':'dagger_monitor','schedule':'*/10_*_*_*_*','action':'check_iter_progress','status':'active'},{'job':'github_push','schedule':'*/5_*_*_*_*','action':'push_milestone_services','status':'active'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
