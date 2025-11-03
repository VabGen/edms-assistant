from typing import Annotated, Optional, Sequence, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from uuid import UUID


# class Plan(BaseModel):
#     next_agent: Literal["document", "attachment", "employee", "default"]
#     agent_input: dict = Field(default_factory=dict)
#     requires_clarification: bool = False

class GlobalState(TypedDict):
    user_id: UUID
    service_token: str
    user_message: str
    messages: Annotated[Sequence[dict], add_messages]
    # plan: Optional[Plan]
    next_agent: Optional[Literal["document", "attachment", "employee", "default"]]
    agent_input: Optional[dict]
    requires_clarification: Optional[bool]
    sub_agent_result: Optional[dict]
    requires_human_input: bool
    error: Optional[str]
    uploaded_file_path: Optional[str]
    uploaded_file_name: Optional[str]
    attachment_id: Optional[str]
    attachment_name: Optional[str]
    document_id: Optional[str]
    current_document: Optional[dict]