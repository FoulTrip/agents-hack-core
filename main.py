import asyncio
import sys
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agents.orchestrator.agent import create_orchestrator
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

async def send_message(runner, session_service, session_id, user_id, message: str) -> str:
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=message)]
        ),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                response_text = event.content.parts[0].text
    return response_text

async def create_fresh_session(session_service, user_id: str):
    session = await session_service.create_session(
        app_name="software-factory",
        user_id=user_id,
    )
    return session

async def run(user_input: str):
    settings.validate()

    agent = create_orchestrator()
    session_service = InMemorySessionService()
    user_id = "user_01"

    logger.info(f"Iniciando pipeline para: {user_input}")

    print("\n" + "="*50)
    print("FASE 1 — Generando requerimientos...")
    print("="*50)
    session1 = await create_fresh_session(session_service, user_id)
    runner1 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response1 = await send_message(runner1, session_service, session1.id, user_id, user_input)
    print(response1)

    print("\n" + "="*50)
    print("FASE 2 — Generando arquitectura...")
    print("="*50)
    session2 = await create_fresh_session(session_service, user_id)
    runner2 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response2 = await send_message(
        runner2, session_service, session2.id, user_id,
        f"Contexto del proyecto: {user_input}\n\nRequerimientos generados:\n{response1}\n\nProcede con el architecture_agent para diseñar la arquitectura técnica."
    )
    print(response2)

    print("\n" + "="*50)
    print("FASE 3 — Generando código y repositorio...")
    print("="*50)
    session3 = await create_fresh_session(session_service, user_id)
    runner3 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response3 = await send_message(
        runner3, session_service, session3.id, user_id,
        f"Contexto del proyecto: {user_input}\n\nArquitectura definida:\n{response2}\n\nProcede con el development_agent. Crea el repositorio en GitHub y sube todos los archivos del proyecto."
    )
    print(response3)

    print("\n" + "="*50)
    print("FASE 4a — Generando tests...")
    print("="*50)
    session4 = await create_fresh_session(session_service, user_id)
    runner4 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response4 = await send_message(
        runner4, session_service, session4.id, user_id,
        f"Contexto del proyecto: {user_input}\n\nArquitectura:\n{response2}\n\nDesarrollo completado:\n{response3}\n\nProcede con el qa_agent. Genera el suite de tests y súbelos al repositorio de GitHub creado."
    )
    print(response4)

    print("\n" + "="*50)
    print("FASE 4b — Generando documentación...")
    print("="*50)
    session5 = await create_fresh_session(session_service, user_id)
    runner5 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response5 = await send_message(
        runner5, session_service, session5.id, user_id,
        f"Contexto del proyecto: {user_input}\n\nArquitectura:\n{response2}\n\nDesarrollo completado:\n{response3}\n\nProcede con el documentation_agent. Genera la documentación completa y súbela al repositorio de GitHub."
    )
    print(response5)

    print("\n" + "="*50)
    print("FASE 5 — Configurando infraestructura DevOps...")
    print("="*50)
    session6 = await create_fresh_session(session_service, user_id)
    runner6 = Runner(agent=agent, app_name="software-factory", session_service=session_service)
    response6 = await send_message(
        runner6, session_service, session6.id, user_id,
        f"Contexto del proyecto: {user_input}\n\nArquitectura:\n{response2}\n\nDesarrollo completado:\n{response3}\n\nProcede con el devops_agent. Genera toda la infraestructura de CI/CD, Docker y despliegue. Súbela al mismo repositorio de GitHub."
    )
    print(response6)

    print("\n" + "="*50)
    print("Pipeline completado. Software Factory finalizado.")
    print("="*50)

if __name__ == "__main__":
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Crea una API REST para gestionar tareas"
    asyncio.run(run(user_input))