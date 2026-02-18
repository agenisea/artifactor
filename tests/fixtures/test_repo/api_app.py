"""Sample FastAPI application for testing API discovery."""

from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/users")
def create_user(name: str, email: str):
    return {"name": name, "email": email}
