import datetime,fastapi,uvicorn
PORT=8851
SERVICE="community_ambassador_program"
DESCRIPTION="Community ambassador program — robotics researchers as OCI Robot Cloud advocates"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/program")
def program(): return {"name":"OCI Robot Cloud Ambassadors","target":"PhD students + postdocs at top robotics labs","benefits":["Free GPU credits ($500/month)","Early access to new features","Co-authorship on benchmarks","GTC speaking opportunity"],"responsibilities":["1 blog post/quarter","GitHub demo","LinkedIn post at launch"],"target_ambassadors":20,"launch":"July 2026","source_labs":["Stanford IPRL","CMU RI","MIT CSAIL","Berkeley RAIL","ETH RSL"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
