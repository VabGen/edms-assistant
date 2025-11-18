# tests/test_agents.py
import pytest
from unittest.mock import AsyncMock, patch
from src.edms_assistant.core.state import GlobalState
from src.edms_assistant.agents.employee_agent import EmployeeAgent
from src.edms_assistant.agents.document_agent import DocumentAgent
from src.edms_assistant.agents.attachment_agent import AttachmentAgent
from src.edms_assistant.agents.main_planner_agent import MainPlannerAgent
from uuid import UUID

@pytest.mark.asyncio
async def test_employee_agent_process_success():
    agent = EmployeeAgent()
    state = GlobalState(
        user_id=UUID("12345678-1234-5678-1234-567812345678"),
        service_token="test_token",
        user_message="Найти Иванова Ивана",
        messages=[]
    )

    with patch('src.edms_assistant.tools.employee.find_responsible_tool.ainvoke') as mock_tool:
        mock_tool.return_value = '[{"id": "87654321-4321-8765-4321-876543210987", "first_name": "Иван", "last_name": "Иванов"}]'
        result = await agent.process(state)

    assert result["messages"][-1].content == "Найден сотрудник: Иван Иванов"
    assert result["requires_clarification"] is False

