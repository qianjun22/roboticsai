import datetime,fastapi,uvicorn
PORT=8345
SERVICE="product_license_request"
DESCRIPTION="OCI product license request tracker"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/status')
def s(): return {'request':'License_OCI_Robot_Cloud_as_official_OCI_product','current_status':'personal_project_on_OCI_allocation','risk_without_license':'cant_sell_externally_no_support_structure','asks':['official_product_designation','engineering_support','sales_enablement','legal_okd_to_sell'],'revenue_upside':'M_ARR_by_2027'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
