import datetime,fastapi,uvicorn
PORT=8278
SERVICE="robot_marketplace_v2"
DESCRIPTION="Robot policy marketplace v2 — buy/sell fine-tuned policies"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/listings')
def listings(): return [{'task':'pick_place_cube','base_model':'GR00T_N1.6','sr':0.65,'price_per_use':0.50},{'task':'pour_liquid','base_model':'GR00T_N1.6','sr':0.55,'price_per_use':0.75}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
