import datetime,fastapi,uvicorn
PORT=8946
SERVICE="cost_transparency_dashboard"
DESCRIPTION="Cost transparency dashboard — real-time GPU cost tracking per customer"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/metrics")
def metrics(): return {"dashboard_sections":[{"section":"Fine-Tune Cost","metrics":["cost_per_run","total_runs_this_month","total_spend"]},{"section":"DAgger Cost","metrics":["cost_per_iter","total_iters","expert_query_cost"]},{"section":"Inference Cost","metrics":["cost_per_1k_queries","total_queries","p99_latency"]},{"section":"Storage","metrics":["checkpoint_storage_gb","training_data_gb","cost_per_gb"]}],"export":"CSV + OCI cost reports integration","alerts":"spend alert at 80pct of monthly budget"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
