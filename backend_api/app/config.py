from pydantic_settings import BaseSettings
import os


class Config(BaseSettings):
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:1b")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL")
    LLM_PORT: str = os.getenv("LLM_PORT")
    SYSTEM_PROMPT_PATH: str = "./prompts/system-prompt-concise.txt"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text:v1.5")
    EMBED_BASE_URL: str = os.getenv("EMBED_BASE_URL")
    EMBED_PORT: str = os.getenv("EMBED_PORT")
    CHROMA_DATA_DIR: str = os.getenv("CHROMA_DATA_DIR", "/chroma/data")
    # Chunking strategy: "fixed" for size-based chunks,
    # "semantic" for structure-aware
    CHUNKING_STRATEGY: str = os.getenv("CHUNKING_STRATEGY", "fixed")

    def __getattr__(self, item):
        """
        Fallback for attributes not defined in the class.
        """
        return ""


config = Config()
