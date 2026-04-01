import datetime,fastapi,uvicorn
PORT=8108
SERVICE="sr_trend_monitor"
DESCRIPTION="Success Rate trend monitor across DAgger runs"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/history")
def history():
    return [
        {"run":"BC_baseline","sr":0.05,"episodes":1000,"date":"2026-01","notes":"1000 demos, closed-loop eval"},
        {"run":"dagger_run5","sr":0.05,"episodes":50,"date":"2026-02","notes":"server kill bug - expert only"},
        {"run":"dagger_run6","sr":0.05,"episodes":50,"date":"2026-02","notes":"server kill bug - expert only"},
        {"run":"dagger_run7","sr":0.05,"episodes":50,"date":"2026-03","notes":"server restart fix partially applied - iters 2-4 expert only"},
        {"run":"dagger_run8","sr":"in_progress","episodes":"~300_projected","date":"2026-04",
         "notes":"beta_decay_0.03_bug=only_iter1_true_dagger; /act_warmup_fix_applied_for_run9",
         "expected_sr":"5-15%"},
        {"run":"dagger_run9","sr":"planned","episodes":450,"date":"2026-04_planned",
         "notes":"beta_decay=0.80_corrected; /act_warmup; 75ep/iter x 6 iters",
         "target_sr":"15-30%"},
        {"run":"dagger_run10","sr":"planned","episodes":600,"date":"2026-05_planned",
         "notes":"curriculum tasks; beta_start=0.5","target_sr":"30-50%"},
        {"run":"dagger_run11","sr":"planned","episodes":1000,"date":"2026-06_planned",
         "notes":"10 iters; multi-task; target AI World demo","target_sr":"65%+"},
    ]
@app.get("/current")
def current():
    return {
        "active_run":"dagger_run8",
        "iteration":"3/6",
        "total_episodes_so_far":99,
        "latest_sr":0.05,
        "trajectory":"improving",
        "next_eval_after_iter":6,
        "ai_world_target_sr":0.65,
        "ai_world_date":"2026-09-15"
    }
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
