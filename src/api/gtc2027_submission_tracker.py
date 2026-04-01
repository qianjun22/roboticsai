import datetime,fastapi,fastapi.responses,uvicorn
PORT=8107
SERVICE="gtc2027_submission_tracker"
DESCRIPTION="GTC 2027 Talk Submission Tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
SUBMISSION={
    "title":"OCI Robot Cloud: From 5% to 65%+ Closed-Loop Success with DAgger + GR00T N1.6",
    "authors":["Jun Qian (Oracle OCI)"],
    "track":"Robotics & Embodied AI",
    "format":"45-min talk + live demo",
    "status":"draft","deadline":"2026-10-01",
    "abstract_words":300,"demo_ready":False,
}
MILESTONES=[
    {"item":"Abstract draft","done":True},
    {"item":"Demo video 3min","done":False},
    {"item":"Co-presenter confirmed (NVIDIA)","done":False},
    {"item":"Submission portal open","done":False},
]
@app.get("/submission")
def submission(): return SUBMISSION
@app.get("/checklist")
def checklist(): return MILESTONES

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
