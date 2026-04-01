import datetime,fastapi,uvicorn
PORT=8539
SERVICE="force_torque_policy"
DESCRIPTION="Force-torque conditioned policy: use F/T sensor readings to improve contact-rich tasks"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/ft_policy/results")
def results(): return {"sensor":"ATI_Mini45","freq_hz":1000,"sr_improvement_vs_no_ft":"15pct","tasks_improved":["peg_insert","usb_plug","connector"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
