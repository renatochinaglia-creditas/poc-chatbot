import os
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from utils.llm import ask_the_llm_with_rag

# enable Agent Observability
from ddtrace.llmobs import LLMObs

LLMObs.enable(
    ml_app=os.getenv("DD_LLMOBS_ML_APP"),
    api_key=os.getenv("DD_API_KEY"),
    site=os.getenv("DD_SITE"),
)

app = FastAPI()


@app.get("/ask")
def ask(prompt: str | None):
    """
    Endpoint to send a prompt to the LLM and return a generated response.
    """
    if not prompt:
        return Response(
            content="Did you have a question?", media_type="application/json"
        )
    response = ask_the_llm_with_rag(prompt)  # New LLM call with RAG
    return Response(content=response, media_type="application/json")


@app.get("/health")
def health():
    """
    Health check endpoint.
    """
    return JSONResponse(content={"status": "ok"}, status_code=200)
