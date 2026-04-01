import datetime,fastapi,uvicorn
PORT=8428
SERVICE="robot_generalization_v2"
DESCRIPTION="Robot generalization v2 — novel objects and environments"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get('/benchmarks')
def b(): return {'seen_cube_sr':0.05,'unseen_cube_color_sr':'TBD','unseen_table_height_sr':'TBD','novel_object_sr':'TBD','target_after_run11':'seen_65pct_unseen_30pct','current_limitation':'fine_tuned_only_on_single_cube'}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
