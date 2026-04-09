import asyncio
import os
import sys
from typing import Any, cast

# Asegurar que el script puede importar los módulos del backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.db import db_manager

async def seed_github_repos():
    # Conectar usando el manager del sistema
    await db_manager.connect()
    
    # 1. Obtener la sesión más reciente
    session = await db_manager.client.projectsession.find_first(
        order={"createdAt": "desc"}
    )
    
    if not session:
        print("No se encontró ninguna sesión activa.")
        await db_manager.disconnect()
        return

    print(f"Generando repositorios para: {session.title}")
    
    sample_repos = [
        {"name": "tripkode-core-api", "fullName": "TripKode/tripkode-core-api", "url": "https://github.com/TripKode/tripkode-core-api"},
        {"name": "tripkode-ui-kit", "fullName": "TripKode/tripkode-ui-kit", "url": "https://github.com/TripKode/tripkode-ui-kit"},
        {"name": "smart-contracts-v1", "fullName": "TripKode/smart-contracts-v1", "url": "https://github.com/TripKode/smart-contracts-v1"},
        {"name": "data-pipeline-exporter", "fullName": "TripKode/data-pipeline-exporter", "url": "https://github.com/TripKode/data-pipeline-exporter"},
        {"name": "auth-bridge-service", "fullName": "TripKode/auth-bridge-service", "url": "https://github.com/TripKode/auth-bridge-service"},
        {"name": "landing-page-v2", "fullName": "TripKode/landing-page-v2", "url": "https://github.com/TripKode/landing-page-v2"},
        {"name": "iot-monitor-dashboard", "fullName": "TripKode/iot-monitor-dashboard", "url": "https://github.com/TripKode/iot-monitor-dashboard"},
        {"name": "legacy-adapter", "fullName": "TripKode/legacy-adapter", "url": "https://github.com/TripKode/legacy-adapter"},
        {"name": "crypto-wallet-integration", "fullName": "TripKode/crypto-wallet-integration", "url": "https://github.com/TripKode/crypto-wallet-integration"},
        {"name": "ai-model-serving", "fullName": "TripKode/ai-model-serving", "url": "https://github.com/TripKode/ai-model-serving"},
    ]
    
    count = 0
    for repo_data in sample_repos:
        # Usar session.id para la relación
        await db_manager.client.githubrepo.create(
            data=cast(
                Any,
                {
                    "sessionId": session.id,
                    **repo_data
                }
            )
        )
        count += 1
        print(f"Añadido: {repo_data['name']}")
    
    print(f"\nOperación completada. {count} repositorios inyectados en la DB vinculados a la sesión {session.sessionId}.")
    await db_manager.disconnect()

if __name__ == "__main__":
    asyncio.run(seed_github_repos())
