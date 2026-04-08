import asyncio
import sys
import os

# Añadir el directorio actual al path para importar modelos
sys.path.append(os.getcwd())

from core.db import db_manager
from models.SessionManager import SessionManager

async def repair():
    sm = SessionManager()
    await db_manager.connect()
    print("Conectado a la DB...")
    
    session_id = '7395f134-8086-4df9-8a09-2835622c9270'
    name = 'collaborators-api'
    url = 'https://github.com/FoulTrip/collaborators-api'
    full_name = 'FoulTrip/collaborators-api'
    
    await sm.link_github_repo(session_id, name, url, full_name)
    print(f"Reparación completada para la sesión {session_id}")
    
    await db_manager.disconnect()

if __name__ == '__main__':
    asyncio.run(repair())
