import datetime,fastapi,uvicorn
PORT=8610
SERVICE="robot_cloud_competitive_moat"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0")
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/moat")
def moat(): return {"moats":[
  {"type":"data_flywheel","description":"each customer fine-tune improves next customer baseline","strength":"high"},
  {"type":"nvidia_partnership","description":"OCI as preferred cloud in NVIDIA robotics ecosystem","strength":"high"},
  {"type":"oci_cost_advantage","description":"9.6x cheaper than AWS p4d — structural OCI pricing edge","strength":"high"},
  {"type":"dagger_ip","description":"online DAgger loop purpose-built for GR00T N1.6","strength":"medium"},
  {"type":"first_mover","description":"only robotics fine-tune cloud on OCI A100 as of March 2026","strength":"medium"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
