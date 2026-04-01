import datetime,fastapi,uvicorn
PORT=8414
SERVICE="domain_randomization_v3"
DESCRIPTION="Domain randomization v3 — texture, lighting, dynamics"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/params')
def p(): return {'cube_color_range':'RGB_any','lighting_intensity':[0.5,2.0],'table_texture':'random_from_50_textures','camera_noise_std':0.01,'joint_friction_range':[0.8,1.2],'enabled':True}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
