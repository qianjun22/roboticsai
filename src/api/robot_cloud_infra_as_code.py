import datetime,fastapi,uvicorn
PORT=8785
SERVICE="robot_cloud_infra_as_code"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/iac")
def iac(): return {"tools":["Terraform","OCI_Resource_Manager"],
  "modules":["vpc","gpu_node","object_storage","vault","monitoring"],
  "ci_cd":"GitHub_Actions_apply_on_merge"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
