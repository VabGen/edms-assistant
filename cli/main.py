# src/edms_assistant/cli/main.py
import asyncio
import typer
from typing_extensions import Annotated
from src.edms_assistant.core.document_indexer import DocumentIndexer
from src.edms_assistant.infrastructure.llm.llm import get_llm
from src.edms_assistant.core.settings import settings

app = typer.Typer()


@app.command()
def index(
        service_token: Annotated[str, typer.Option("--token", "-t",
                                                   help="Service token for EDMS API")] = settings.service_token_for_indexing,
        index_path: Annotated[
            str, typer.Option("--path", "-p", help="Path to save FAISS index")] = settings.faiss_index_path,
        embeddings_model: Annotated[
            str, typer.Option("--emb-model", help="Embeddings model to use")] = settings.llm_model_name,
        # Используем LLM для эмбеддингов
):
    """
    Индексирует документы из EDMS в FAISS векторный индекс.
    """
    if not service_token:
        typer.echo("Ошибка: Необходимо указать --token или задать service_token_for_indexing в настройках.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Запускаю индексацию документов...")
    typer.echo(f"  - Service Token: {'*' * len(service_token)} (скрыт)")
    typer.echo(f"  - Index Path: {index_path}")
    typer.echo(f"  - Embeddings Model: {embeddings_model}")

    try:
        # Инициализируем эмбеддер (можем использовать LLM, или отдельный эмбеддер)
        # embeddings = HuggingFaceEmbeddings(model_name=embeddings_model) # или SentenceTransformer
        # Пока используем эмбеддер из LLM (он должен поддерживать .embed_query)
        llm_client = get_llm()
        embeddings = llm_client  # или llm_client.client, в зависимости от реализации

        indexer = DocumentIndexer(embeddings=embeddings, vector_store_path=index_path)
        asyncio.run(indexer.index_all_documents(service_token=service_token))
        typer.echo(f"✅ Индексация завершена. Индекс сохранён в {index_path}")

    except KeyboardInterrupt:
        typer.echo("\n❌ Индексация прервана пользователем.", err=True)
    except Exception as e:
        typer.echo(f"❌ Ошибка при индексации: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def health():
    """
    Проверяет состояние ассистента (например, доступность LLM, индекса).
    """
    typer.echo("Проверка состояния ассистента...")
    try:
        # Простая проверка LLM
        llm = get_llm()
        # Простая проверка индекса
        from src.edms_assistant.core.rag_retriever import RAGRetriever
        retriever = RAGRetriever()
        if retriever.vector_store:
            typer.echo("✅ Индекс загружен.")
        else:
            typer.echo("⚠️ Индекс не загружен. Запустите 'edms-assistant index'.")
        typer.echo("✅ LLM доступен.")
        typer.echo("✅ Ассистент готов к работе.")
    except Exception as e:
        typer.echo(f"❌ Ошибка проверки состояния: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
