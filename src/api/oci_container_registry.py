import datetime,fastapi,uvicorn
PORT=8374
SERVICE="oci_container_registry"
DESCRIPTION="OCI Container Registry — Docker images for robot services"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/images')
def i(): return [{'name':'robot-inference','tag':'latest','size_gb':8.2,'base':'NVIDIA_PyTorch_2.3'},{'name':'dagger-trainer','tag':'latest','size_gb':12.4,'base':'NVIDIA_PyTorch_2.3+IsaacGR00T'},{'name':'genesis-sim','tag':'latest','size_gb':6.8,'base':'CUDA_12.1'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
