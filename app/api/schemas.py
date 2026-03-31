from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str
    database: str
    openai: str


class ReindexResponse(BaseModel):
    status: str
    nodes_indexed: int
