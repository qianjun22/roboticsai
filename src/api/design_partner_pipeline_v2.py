import datetime,fastapi,fastapi.responses,uvicorn
PORT=8101
SERVICE="design_partner_pipeline_v2"
DESCRIPTION="Design Partner Pipeline v2 - Series B+ robotics startup tracking"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
PARTNERS=[
    {"company":"Machina Labs","stage":"active-pilot","arr":120000,"contact":"Edward Mehr","nr_ref":True},
    {"company":"Apptronik","stage":"eval","arr":180000,"contact":"Jeff Cardenas","nr_ref":True},
    {"company":"Figure AI","stage":"intro","arr":300000,"contact":"Brett Adcock","nr_ref":False},
    {"company":"1X Technologies","stage":"prospect","arr":240000,"contact":"Bernt Bornich","nr_ref":False},
    {"company":"Agility Robotics","stage":"prospect","arr":200000,"contact":"Damion Shelton","nr_ref":False},
]
@app.get("/partners")
def partners(): return PARTNERS
@app.get("/pipeline")
def pipeline(): return {"total_arr_potential":sum(p["arr"] for p in PARTNERS),"active":sum(1 for p in PARTNERS if p["stage"]=="active-pilot")}

@app.get("/health")
def health():
    return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
