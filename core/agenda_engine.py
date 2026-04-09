import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.db import db_manager
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)

agenda_scheduler = AsyncIOScheduler()

async def trigger_standup_event(meeting):
    """
    Teletransporta a los agentes a la Sala de Conferencias y dispara un registro.
    Esta función simula la integración con el motor Claw3D (Colyseus).
    """
    logger.info(f"[WORKFLOW] Iniciando '{meeting.title}' (ID: {meeting.id})")
    
    try:
        # 1. Recuperar los agentes activos del usuario
        agents = await db_manager.client.agent.find_many(
            where={"userId": meeting.userId, "active": True}
        )
        
        logger.info(f"[CLAW3D] Notificando a {len(agents)} agentes para moverse a: {meeting.location}")
        
        # 2. Aquí crearíamos una sesión de charla temporal si fuesen a hablar
        # Por ahora creamos un "AgentActivity" para cada uno, marcándolo como en Standup
        # Asi el endpoint /api/office/presence de Claw3D los mostrará en reunión.
        from models.SessionManager import SessionManager
        sm = SessionManager()
        
        for agent in agents:
            # Fake session ID for standup
            standup_session_id = f"standup_factory_{meeting.id}"
            
            # Registrar actividad para que la UI 3D los muestre ocupados
            activity = await db_manager.client.agentactivity.create(
                data={
                    "sessionId": standup_session_id,
                    "agentName": agent.name,
                    "agentRole": agent.role,
                    "taskDescription": f"Participando en {meeting.title}",
                    "status": "working" # En Claw3D esto cambiará su animación / estado
                }
            )
            logger.info(f"    - Agente {agent.name} entró a la sala de reuniones.")
            
        # Actualizamos la fecha de última ejecución
        await db_manager.client.standupmeeting.update(
            where={"id": meeting.id},
            data={"lastRunAt": datetime.now(timezone.utc)}
        )
        logger.info("Reunion iniciada correctamente.")

    except Exception as e:
        logger.error(f"Error lanzando evento de Standup: {e}")

async def check_and_execute_standups():
    """
    Servicio de fondo (Polling) que revisa si hay reuniones pendientes para la hora actual.
    """
    try:
        # Recuperamos todas las reuniones activas
        standups = await db_manager.client.standupmeeting.find_many(where={"active": True})
        
        now = datetime.utcnow()
        # Formato HH:MM
        current_time_str = now.strftime("%H:%M")
        
        for meeting in standups:
            if meeting.time == current_time_str:
                # Verificamos si ya corrió hoy para no lanzarlo varias veces en este minuto
                if meeting.lastRunAt and meeting.lastRunAt.date() == now.date():
                    continue
                    
                await trigger_standup_event(meeting)
                
    except Exception as e:
        logger.error(f"Error procesando el cron de standups: {e}")

def start_scheduler():
    """
    Inicializa el APScheduler para revisar la agenda cada minuto.
    """
    logger.info("Iniciando Motor de Agendas de Agentes (Cron-Job)")
    # El trigger de minuto='*' correrá al inicio de cada minuto
    agenda_scheduler.add_job(check_and_execute_standups, CronTrigger(minute="*"))
    agenda_scheduler.start()
