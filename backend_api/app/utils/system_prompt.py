from config import config


def get_system_prompt() -> str:
    """
    Returns the system prompt for the LLM
    """
    with open(config.SYSTEM_PROMPT_PATH, "r") as file:
        return file.read()
