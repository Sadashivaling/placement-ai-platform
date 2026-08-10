from fastapi import FastAPI

app = FastAPI(
    title="Placement AI Platform",
    description="AI-powered placement and job readiness platform",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Placement AI Platform API is running",
        "status": "success"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
