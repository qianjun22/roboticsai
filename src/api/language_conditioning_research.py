import datetime,fastapi,uvicorn
PORT=8841
SERVICE="language_conditioning_research"
DESCRIPTION="Language conditioning research — natural language task specification for run14+"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/research")
def research(): return {"goal":"condition GR00T policy on natural language task descriptions","approach":"CLIP text encoder for task embedding","tasks":["pick_cube","place_cube_on_table","stack_two_cubes","hand_cube_to_human"],"integration":"concatenate lang embedding with visual obs","planned_run":"run14","prerequisite":"run12 F/T sensor baseline","paper_target":"ICRA 2027 submission (Sept 2026)","related_work":["RT-2","SayCan","CLIP-Fields","GR00T N2"]}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
