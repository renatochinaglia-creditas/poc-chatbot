from fastapi import FastAPI, Response
from utils.llm import ask_the_llm

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
    response = ask_the_llm(prompt)
    return Response(content=response, media_type="application/json")


@app.get("/health")
def health_check():
    """
    Simple health check endpoint that returns a 200 status code.
    """
    return Response(content="OK", media_type="text/plain")
