import datetime,fastapi,uvicorn
PORT=22643
SERVICE="arxiv_hn_moment"
DESCRIPTION="HN moment: Show HN post Jun 21 -- 200 upvotes -- front page 4hrs -- 1200 GitHub stars in 48hrs"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/{endpoint}")
def ep(): return {"service":SERVICE,"description":DESCRIPTION,"port":PORT}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
