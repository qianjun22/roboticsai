import datetime,fastapi,uvicorn
PORT=8582
SERVICE="robot_demo_video_generator"
DESCRIPTION="Demo video generator: capture robot episodes, edit, compress, upload to S3 for demos"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/videos/list")
def videos(): return {"videos":[{"id":"run9_demo","sr":0.28,"size_mb":2.1},{"id":"run8_eval","sr":0.10,"size_mb":1.8}],"total":4,"views":1240}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
