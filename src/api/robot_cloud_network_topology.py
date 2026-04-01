import datetime,fastapi,uvicorn
PORT=8787
SERVICE="robot_cloud_network_topology"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/topology")
def topology(): return {"vcn":"robot-cloud-vcn",
  "subnets":[{"name":"public_lb","cidr":"10.0.1.0/24"},{"name":"gpu_nodes","cidr":"10.0.2.0/24"}],
  "rdma_for_multi_gpu":True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
