# src/edms_assistant/main.py
import asyncio
import logging
from dotenv import load_dotenv
from src.edms_assistant.utils.logging import setup_logging
from src.edms_assistant.config.settings import settings
from src.edms_assistant.presentation.api import app

load_dotenv()
setup_logging()

logger = logging.getLogger(__name__)

async def initialize_agent():
    logger.info("Initializing EDMS Assistant Agent...")
    logger.info("EDMS Assistant Agent initialized.")

async def main():
    logger.info("Starting EDMS Assistant...")
    await initialize_agent()

if __name__ == "__main__":
    asyncio.run(main())


# main.py

# import logging
# import json
# from dbm import error
# from typing import Optional, Dict, Any, List
# from uuid import UUID
# import asyncio
#
# import httpx
# import redis.asyncio as redis_async
# import aio_pika
# import uvicorn
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Security, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from pydantic import BaseModel, Field
# # from jose import JWT
# from transformers import pipeline
# from langchain_core.messages import BaseMessage
# # jwt, JWTError
# # Logger
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
#
# # JWT Config
# SECRET_KEY = "your-secret-key"
# ALGORITHM = "HS256"
#
# # FastAPI app
# app = FastAPI(title="EDMS Intelligent AI Assistant with NLP and Distributed Systems", version="2.0.0")
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# security = HTTPBearer()
#
# # Redis client for caching and deduplication
# redis_client = redis_async.Redis(host="localhost", port=6379, db=0)
#
# # RabbitMQ connection parameters
# RABBITMQ_URL = "amqp://guest:guest@localhost/"
# from src.edms_assistant.infrastructure.llm.llm import get_llm
# # Hugging Face zero-shot classifier (or OpenAI GPT via API)
# classifier = get_llm()
#
#
# class GlobalState(BaseModel):
#     user_id: UUID
#     service_token: str
#     document_id: Optional[str] = None
#     user_message: str
#     uploaded_file_path: Optional[str] = None
#     messages: List[BaseMessage] = []
#     requires_clarification: bool = False
#     clarification_context: Optional[Dict[str, Any]] = None
#     current_agent: str = "main_planner_agent"
#     agent_context: Dict[str, Any] = Field(default_factory=dict)
#     available_agents: List[str] = Field(default_factory=list)
#     error: Optional[str] = None


# def get_user_role_from_token(token: str) -> str:
#     try:
#         payload = JWT.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload.get("role", "")
#     except error:
#         return ""


# def check_access(role: str, allowed_roles: List[str]) -> None:
#     if role not in allowed_roles:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied: insufficient rights."
#         )
#
#
# class EdmsApiClient:
#     def __init__(self, base_url: str, token: str):
#         self.base_url = base_url.rstrip("/")
#         self.token = token
#         self.client = httpx.AsyncClient(timeout=10)
#
#     def get_headers(self):
#         return {"Authorization": f"Bearer {self.token}"}
#
#     async def get_document(self, document_id: UUID) -> Optional[Dict[str, Any]]:
#         url = f"{self.base_url}/api/document/{document_id}"
#         response = await self.client.get(url, headers=self.get_headers())
#         response.raise_for_status()
#         return response.json()
#
#     async def search_documents(self, query: str) -> Dict[str, Any]:
#         url = f"{self.base_url}/api/document"
#         response = await self.client.get(url, params={"query": query}, headers=self.get_headers())
#         response.raise_for_status()
#         return response.json()
#
#     async def close(self):
#         await self.client.aclose()
#
#
# class BaseAgent:
#     def __init__(self, api_client: EdmsApiClient):
#         self.api_client = api_client
#
#     async def process(self, state: GlobalState) -> Dict[str, Any]:
#         raise NotImplementedError
#
#
# # DocumentAgent with NLP intent analysis via Hugging Face zero-shot classification
# class DocumentAgent(BaseAgent):
#     async def process(self, state: GlobalState) -> Dict[str, Any]:
#         labels = ["search document", "get document", "update document", "unknown"]
#         classification = classifier(state.user_message, labels)
#         intent = classification["labels"][0]
#
#         if intent == "search document":
#             results = await self.api_client.search_documents(state.user_message)
#             count = len(results.get("items", [])) if results else 0
#             res_text = f"Найдено документов: {count}." if count > 0 else "Документы не найдены."
#             return {
#                 "messages": [BaseMessage(role="assistant", content=res_text)],
#                 "requires_clarification": False
#             }
#         elif intent == "get document" and state.document_id:
#             doc = await self.api_client.get_document(state.document_id)
#             content = json.dumps(doc, ensure_ascii=False, indent=2) if doc else "Документ не найден."
#             return {
#                 "messages": [BaseMessage(role="assistant", content=content)],
#                 "requires_clarification": False
#             }
#
#         return {"messages": [BaseMessage(role="assistant", content="Извините, не понял запрос.")], "requires_clarification": False}
#
#
# # AgentManager dynamically invokes registered agents
# class AgentManager:
#     def __init__(self, api_client: EdmsApiClient):
#         self.api_client = api_client
#         self.agents = {
#             "document_agent": DocumentAgent(self.api_client),
#             # Добавьте других агентов сюда, например "employee_agent", "attachment_agent" и т.д.
#         }
#
#     async def handle_request(self, state: GlobalState) -> Dict[str, Any]:
#         agent_key = state.current_agent
#         agent = self.agents.get(agent_key)
#         if not agent:
#             return {
#                 "messages": [BaseMessage(role="assistant", content="Агент не найден.")],
#                 "requires_clarification": False,
#                 "error": "Agent not found"
#             }
#         return await agent.process(state)
#
#
# # RabbitMQ task queue integration for asynchronous agent task execution
# async def publish_task_to_queue(message: Dict[str, Any], routing_key: str = "agent_tasks"):
#     connection = await aio_pika.connect_robust(RABBITMQ_URL)
#     async with connection:
#         channel = await connection.channel()
#         await channel.declare_queue("agent_tasks", durable=True)
#         await channel.default_exchange.publish(
#             aio_pika.Message(body=json.dumps(message).encode()),
#             routing_key=routing_key
#         )
#
#
# async def consume_tasks():
#     connection = await aio_pika.connect_robust(RABBITMQ_URL)
#     channel = await connection.channel()
#     queue = await channel.declare_queue("agent_tasks", durable=True)
#
#     async with queue.iterator() as queue_iter:
#         async for message in queue_iter:
#             async with message.process():
#                 task_data = json.loads(message.body)
#                 logger.info(f"Processing task: {task_data}")
#                 # TODO: реализовать вызов агента согласно task_data
#                 # Здесь можно выполнять вызовы агентов и обновлять состояние
#
#
# @app.post("/chat")
# async def chat_endpoint(
#         user_message: str = Form(...),
#         service_token: str = Form(...),
#         user_id: str = Form(...),
#         document_id: Optional[str] = Form(None),
#         agent_type: str = Form("document_agent"),
#         credentials: HTTPAuthorizationCredentials = Security(security),
#         file: Optional[UploadFile] = File(None)
# ):
#     # role = get_user_role_from_token(credentials.credentials)
#     # check_access(role, allowed_roles=["user", "admin"])
#
#     try:
#         validated_user_id = UUID(user_id)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid user_id format")
#
#     # Дедупликация запросов по user_id+user_message через Redis
#     cache_key = f"user:{validated_user_id}:msg:{hash(user_message)}"
#     cached = await redis_client.get(cache_key)
#     if cached:
#         logger.info("Returning cached result")
#         return json.loads(cached)
#
#     # Инициализация API клиента
#     api_client = EdmsApiClient("http://edms.api", service_token)
#
#     # Создание глобального состояния
#     state = GlobalState(
#         user_id=validated_user_id,
#         service_token=service_token,
#         document_id=document_id,
#         user_message=user_message,
#         uploaded_file_path=None,
#         messages=[],
#         current_agent=agent_type,
#         available_agents=list(["document_agent"]),
#     )
#
#     manager = AgentManager(api_client)
#
#     # Асинхронная публикация задачи в очередь для масштабируемой обработки
#     task_message = state.dict()
#     await publish_task_to_queue(task_message)
#
#     # Для упрощения примера сразу обрабатываем в синхронном режиме (в реальности обрабатывать нужно отдельно)
#     result = await manager.handle_request(state)
#
#     # Закрываем клиент
#     await api_client.close()
#
#     # Кешируем результат в Redis на 60 секунд
#     response_data = {
#         "response": result["messages"][-1].content if result["messages"] else "Нет ответа.",
#         "requires_clarification": result.get("requires_clarification", False),
#         "error": result.get("error", None),
#     }
#     await redis_client.set(cache_key, json.dumps(response_data), ex=60)
#
#     return response_data
#
#
# @app.get("/health")
# async def health_check():
#     return {"status": "ok", "version": "2.0.0"}
#
#
# # Запуск background задачи по прослушке RabbitMQ (при старте приложения FastAPI)
# @app.on_event("startup")
# async def startup_event():
#     # Запуск consumer в фоне
#     asyncio.create_task(consume_tasks())
