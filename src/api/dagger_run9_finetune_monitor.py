import datetime,fastapi,uvicorn
PORT=8937
SERVICE="dagger_run9_finetune_monitor"
DESCRIPTION="DAgger run9 fine-tune monitor — loss tracking during 7000-step fine-tuning"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/monitor")
def monitor(): return {"run":9,"finetune_config":{"steps":7000,"batch_size":16,"lr":1e-4,"warmup_steps":200},"expected_loss_curve":{"step_0":0.35,"step_1000":0.18,"step_3000":0.12,"step_5000":0.10,"step_7000":0.099},"run8_final_loss":0.099,"convergence_check":"loss < 0.11 at step 5000","early_stop":"if loss plateaus for 500 steps","checkpoint_freq":500}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
