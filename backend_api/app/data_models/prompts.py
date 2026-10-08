from pydantic import BaseModel
from typing import List


class Prompt(BaseModel):
    prompt: str


class DocumentsList(BaseModel):
    documents: List[str]
