import datetime,fastapi,uvicorn
PORT=9026
SERVICE="competitive_pricing_analysis"
DESCRIPTION="Competitive pricing analysis — OCI Robot Cloud vs AWS RoboMaker and Azure"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/analysis")
def analysis(): return {"scenario":"GR00T fine-tune 7000 steps + 6 DAgger iters","OCI_Robot_Cloud":{"price":"$15k/month","includes":"all fine-tune + DAgger + inference","GPU":"A100 80GB"},"AWS":{"training_cost":"$24.78/run * 6 = $148.68","DAgger_custom":"no managed service","total_cost_build":"$50k+ engineering"},"Azure":{"similar_gap":"no GR00T native support"},"conclusion":"OCI is only cloud with managed DAgger-as-a-service + cheapest GPU"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
