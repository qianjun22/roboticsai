import datetime,fastapi,uvicorn
PORT=8400
SERVICE="roadmap_v4"
DESCRIPTION="Tech roadmap v4 — adjusted after DAgger run8 postmortem"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/roadmap')
def r(): return {'q2_2026':['run8_eval','run9_launch_corrected_beta','run10_curriculum_start','design_partner_pilot','NVIDIA_meeting'],'q3_2026':['run11_65pct_sr_target','AI_World_demo','first_customer','public_launch'],'q4_2026':['3_customers','GTC_talk_accepted','real_robot_validation','Series_A_outreach'],'q1_2027':['GTC_2027_talk','Series_A_close','5_customers','run12_multi_task']}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
