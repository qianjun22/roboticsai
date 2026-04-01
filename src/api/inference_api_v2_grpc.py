import datetime,fastapi,uvicorn
PORT=8853
SERVICE="inference_api_v2_grpc"
DESCRIPTION="Inference API v2 with gRPC support — lower latency for real-time robot control"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/spec")
def spec(): return {"v1":{"protocol":"REST/JSON","latency_ms":229,"throughput":"4.4 fps"},"v2":{"protocol":"gRPC + protobuf","latency_target_ms":"<150ms","throughput_target":"8+ fps","streaming":"bidirectional for continuous control"},"use_case":"real-time 30Hz robot control loop","timeline":"August 2026","sdk_update":"oci-robot-cloud>=2.0.0"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
