from fastapi import FastAPI

app = FastAPI(title="Woori-Talk-Banking API")


@app.get("/health")
def health_check():
    return {"status": "ok"}
