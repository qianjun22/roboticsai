import datetime,fastapi,uvicorn
PORT=8947
SERVICE="robot_learning_curriculum_v2"
DESCRIPTION="Robot learning curriculum v2 — progressive task difficulty for faster convergence"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/curriculum")
def curriculum(): return {"concept":"progressive task difficulty for faster DAgger convergence","stages":[{"stage":1,"task":"reach to cube (easy)","target_sr":"90pct","eps":25},{"stage":2,"task":"grasp cube (medium)","target_sr":"80pct","eps":50},{"stage":3,"task":"lift cube to 0.5m","target_sr":"75pct","eps":50},{"stage":4,"task":"lift to 0.78m (hard)","target_sr":"100pct","eps":75}],"benefit":"est 40pct fewer total episodes vs direct training","auto_progress":"advance stage when SR > threshold","timeline":"run20+ (Q3 2027)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
