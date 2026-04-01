import datetime,fastapi,uvicorn
PORT=8386
SERVICE="social_proof_builder"
DESCRIPTION="Social proof builder — testimonials + case studies"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/assets')
def a(): return {'needed':['design_partner_quote','pilot_results_case_study','NVIDIA_logo_permission','oracle_case_study'],'available':['github_commit_history','benchmark_numbers','demo_video'],'target_assets_by':'2026-09-01_for_AI_World'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
