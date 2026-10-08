from pydantic_settings import BaseSettings
import os


class Config(BaseSettings):
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:1b")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL")
    LLM_PORT: str = os.getenv("LLM_PORT")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

    def __getattr__(self, item):
        """
        Fallback for attributes not defined in the class.
        """
        return ""


config = Config()
