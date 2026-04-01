import datetime,fastapi,uvicorn
PORT=8372
SERVICE="oci_functions_v2"
DESCRIPTION="OCI Functions v2 — serverless eval triggers"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/functions')
def f(): return [{'name':'trigger-eval','trigger':'DAgger_checkpoint_saved','action':'start_genesis_eval_20_eps'},{'name':'notify-sr','trigger':'eval_complete','action':'update_sr_monitor_webhook'},{'name':'auto-launch-next-run','trigger':'eval_sr_above_threshold','action':'launch_next_dagger_run'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
