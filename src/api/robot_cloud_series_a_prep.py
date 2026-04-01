import datetime,fastapi,uvicorn
PORT=8609
SERVICE="robot_cloud_series_a_prep"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/deck_outline")
def deck_outline(): return {"target_raise":"$12M","target_close":"Q2-2027",
  "lead_investor_targets":["a16z","Lux_Capital","Eclipse_Ventures","Playground_Global"],
  "proof_points_needed":[
    "65%+ SR at AI World Sept 2026",
    "3+ paying design partners",
    "NVIDIA co-engineering MOU",
    "$500k+ ARR by Q1 2027"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
