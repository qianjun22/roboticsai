import datetime,fastapi,uvicorn
PORT=8343
SERVICE="clay_magouyrk_brief"
DESCRIPTION="Clay Magouyrk (OCI EVP) executive brief — market + GTM"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/brief')
def b(): return {'audience':'Clay_Magouyrk_OCI_EVP','key_ask':'design_partner_intro+product_license','market':'B_embodied_AI_by_2030','oci_differentiation':'NVIDIA_full_stack+9.6x_cost_advantage+US_origin','first_revenue_by':'Sept_2026','oci_gpu_already_allocated':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
