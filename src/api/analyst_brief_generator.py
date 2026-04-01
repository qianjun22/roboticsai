import datetime,fastapi,uvicorn
PORT=8533
SERVICE="analyst_brief_generator"
DESCRIPTION="Analyst brief generator: Gartner/Forrester robotics cloud brief for OCI Robot Cloud"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/brief")
def brief(): return {"target_analysts":["Gartner","Forrester","IDC"],"brief_type":"product_launch","differentiators":["NVIDIA_full_stack","DAgger_online_learning","9.6x_cheaper"],"scheduled":"2026-09-10"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
