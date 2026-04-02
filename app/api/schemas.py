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


class GeneratedServer(BaseModel):
    name: str
    title: str
    version: str
    endpoints: int
    path: str
    mcp_config: dict


class GenerateResponse(BaseModel):
    status: str
    server: GeneratedServer


class GeneratedServerList(BaseModel):
    servers: list[GeneratedServer]


class DeleteResponse(BaseModel):
    status: str
    deleted: str
