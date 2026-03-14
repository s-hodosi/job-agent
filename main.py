from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from agents import run_agents

app = FastAPI()

app.mount("/ui", StaticFiles(directory="static", html=True), name="static")


class JobInput(BaseModel):
    cv: str
    job_description: str


@app.post("/analyze")
def analyze(data: JobInput):

    result = run_agents(
        data.cv,
        data.job_description
    )

    return {"result": result}