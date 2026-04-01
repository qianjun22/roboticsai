import datetime,fastapi,uvicorn
PORT=8889
SERVICE="run14_language_conditioning_impl"
DESCRIPTION="DAgger run14 language conditioning — CLIP text encoder for task specification"
app=fastapi.FastAPI(title=SERVICE,version="1.0.0",description=DESCRIPTION)
@app.get("/health")
def health(): return {"status":"ok","service":SERVICE,"port":PORT,"ts":datetime.datetime.utcnow().isoformat()}
@app.get("/")
def root(): return {"service":SERVICE,"port":PORT,"status":"operational"}
@app.get("/config")
def config(): return {"run":14,"text_encoder":"CLIP ViT-B/32 (text branch only)","embedding_dim":512,"fusion":"concatenate with visual obs before action head","tasks_supported":["pick up the red cube","place the cube on the table","stack the cubes","hand the cube to me"],"training":{"steps":10000,"freeze_clip":True,"train_fusion_layer":True,"train_action_head":True},"expected_sr":"maintain >95pct on pick task + generalize to new instructions","prerequisite":"run13 domain randomization complete"}
if __name__=="__main__": uvicorn.run(app,host="0.0.0.0",port=PORT)
