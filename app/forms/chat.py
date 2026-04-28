from pydantic import BaseModel


class ChatPromptForm(BaseModel):
    """User prompt submitted from the chat form."""

    prompt: str
