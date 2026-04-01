import datetime,fastapi,uvicorn
PORT=8377
SERVICE="oci_networking_config"
DESCRIPTION="OCI networking configuration — VCN + security groups"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/config')
def c(): return {'vcn':'roboticsai-vcn','subnet_private':'10.0.1.0/24','subnet_public':'10.0.0.0/24','open_ports':[8001,8002,22],'bastion_host':True,'ssl_termination':'OCI_Load_Balancer'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
