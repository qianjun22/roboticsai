import datetime,fastapi,fastapi.responses,uvicorn
PORT=8102
SERVICE="ai_world_2026_demo"
DESCRIPTION="AI World Boston 2026 Live Demo - 6-step cube pick-and-place showcase"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
DEMO_STEPS=[
    {"step":1,"name":"System Init","desc":"OCI A100 GPU inference cold start","expected_ms":500},
    {"step":2,"name":"GR00T Load","desc":"Load DAgger run8 checkpoint","expected_ms":2000},
    {"step":3,"name":"Scene Setup","desc":"Genesis sim: Franka + cube spawn","expected_ms":300},
    {"step":4,"name":"Policy Infer","desc":"GR00T N1.6 → 7-DOF action","expected_ms":226},
    {"step":5,"name":"Execute","desc":"Sim step + cube grasp","expected_ms":100},
    {"step":6,"name":"Success Check","desc":"Cube z > 0.78m lift threshold","expected_ms":10},
]
EVENT={"name":"AI World Boston 2026","date":"2026-09-15","booth":"OCI-R42","target_sr":"65%+"}
@app.get("/demo")
def demo(): return {"event":EVENT,"steps":DEMO_STEPS,"total_expected_ms":sum(s["expected_ms"] for s in DEMO_STEPS)}

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
