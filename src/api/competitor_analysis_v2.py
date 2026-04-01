import datetime,fastapi,uvicorn
PORT=8869
SERVICE="competitor_analysis_v2"
DESCRIPTION="Competitor analysis v2 — updated with Physical Intelligence + 1X + Figure AI"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/analysis")
def analysis(): return {"our_position":"cloud infra for 3rd-party robotics teams (not robot OEM)","competitors":{"physical_intelligence":{"focus":"general robot policy","raised":"$400M","differentiation":"own hardware"},"1X_technologies":{"focus":"humanoid robot","raised":"$100M","differentiation":"hardware"},"figure_ai":{"focus":"humanoid","raised":"$675M","note":"not a cloud service"},"hugging_face_lerobot":{"focus":"open-source toolkit","note":"we build on top of this"}},"our_moat":["OCI GPU cost (9.6x cheaper)","NVIDIA ecosystem integration","Oracle enterprise distribution","DAgger online learning as a service"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
