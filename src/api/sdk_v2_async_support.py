import datetime,fastapi,uvicorn
PORT=8860
SERVICE="sdk_v2_async_support"
DESCRIPTION="OCI Robot Cloud SDK v2 — async/await + streaming for real-time control loops"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/features")
def features(): return {"sdk":"oci-robot-cloud>=2.0.0","new":["async RobotCloudClient","streaming inference (gRPC)","batch SDG (parallel genesis envs)","checkpoint auto-download","model registry integration"],"backwards_compatible":True,"python_versions":["3.10","3.11","3.12"],"timeline":"August 2026","example":"async for action in client.stream_policy(obs): robot.step(action)"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
