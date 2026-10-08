import os

import requests
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm
from fastapi import FastAPI
from pydantic import BaseModel

LLM_MODEL = os.environ["LLM_MODEL"]
OLLAMA_URL = f"{os.getenv('LLM_BASE_URL', 'http://host.docker.internal')}:{os.getenv('LLM_PORT', '11434')}"
SYSTEM_PROMPT = (
    "You are the QuantumHound assistant, a travel agency for time travel adventures. "
    "Answer briefly and stay in character."
)

app = FastAPI()


class ChatRequest(BaseModel):
    prompt: str


@llm(model_name=LLM_MODEL, model_provider="ollama", name="ollama_chat")
def ask_ollama(prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    r = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": LLM_MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    answer = r.json()["message"]["content"]
    LLMObs.annotate(
        input_data=messages,
        output_data=[{"role": "assistant", "content": answer}],
    )
    return answer


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    return {"success": True, "message": ask_ollama(req.prompt)}
