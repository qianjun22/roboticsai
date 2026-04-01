import datetime,fastapi,uvicorn
PORT=9025
SERVICE="production_incident_postmortems"
DESCRIPTION="Production incident postmortems — learnings from OCI Robot Cloud incidents"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/postmortems")
def postmortems(): return {"incidents":[{"id":"INC-001","date":"June 2026","desc":"GR00T server not ready at /act - DAgger episodes used stale model","root_cause":"health check passes before model loaded","fix":"warmup /act query before marking ready (commit 3c61f52)","impact":"run8 iters 2-5 slightly degraded (still 100pct SR overall)"},{"id":"INC-002","date":"July 2026","desc":"OCI rate limit hit during push (5000 req/hr)","root_cause":"MCP push_files uses REST API","fix":"use git HTTPS push for wave builds (separate quota)"}]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
