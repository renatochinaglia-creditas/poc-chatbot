from openai import OpenAI
from config import config
from .system_prompt import get_system_prompt

LLM_URL = f"{config.LLM_BASE_URL}:{config.LLM_PORT}/v1"

# Initialize client
openai_client = OpenAI(
    base_url=LLM_URL,
    api_key=config.OPENAI_API_KEY,
)


# Not RAG-enabled, just a straightforward LLM call
def ask_the_llm(prompt: str) -> str:
    """
    Calls the LLM with the user and system prompts.
    """
    system_prompt = get_system_prompt()
    response = openai_client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content
