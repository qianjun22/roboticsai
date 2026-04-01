import datetime,fastapi,uvicorn
PORT=8353
SERVICE="user_research_tracker"
DESCRIPTION="User research tracker — customer discovery interviews"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/interviews')
def i(): return [{'company':'Machina_Labs','type':'design_partner','pain_point':'no_cloud_GPU_for_robot_fine_tuning','willingness_to_pay':3000,'use_case':'sheet_metal_forming'},{'company':'Apptronik','type':'design_partner','pain_point':'GR00T_deployment_complexity','willingness_to_pay':4500,'use_case':'humanoid_manipulation'}]
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
