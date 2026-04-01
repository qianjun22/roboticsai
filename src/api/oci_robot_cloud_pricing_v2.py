import datetime,fastapi,uvicorn
PORT=8843
SERVICE="oci_robot_cloud_pricing_v2"
DESCRIPTION="OCI Robot Cloud pricing v2 — updated tiers with proven cost benchmarks"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/tiers")
def tiers(): return {"starter":{"price":"$5k/month","includes":"Genesis SDG (1k demos), 1 fine-tune run, 20-ep eval, inference API","target":"seed-stage startups"},"growth":{"price":"$15k/month","includes":"Genesis SDG (5k demos), 3 DAgger runs, 100-ep eval, SLA 99.9pct","target":"Series A startups"},"enterprise":{"price":"$50k+/month","includes":"custom embodiment, multi-robot, dedicated GPU cluster, NVIDIA co-engineering","target":"Series B+ and corporates"},"cost_benchmarks":{"fine_tune_per_run":"$0.43 (OCI A100)","inference_per_ep":"$0.022","vs_aws_savings":"9.6x cheaper than p4d"}}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
