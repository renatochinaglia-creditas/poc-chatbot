from openai import OpenAI
from typing import Dict, List
from config import config

LLM_URL = f"{config.LLM_BASE_URL}:{config.LLM_PORT}/v1"

# Initialize client
openai_client = OpenAI(
    base_url=LLM_URL,
    api_key=config.OPENAI_API_KEY,
)


def ask_the_llm(prompt: str) -> str:
    """
    Calls the LLM with the given prompt
    """
    response = openai_client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
