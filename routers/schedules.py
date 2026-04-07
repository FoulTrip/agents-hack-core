from fastapi import APIRouter, Depends, HTTPException
from typing import List, Any, Optional
from core.db import db_manager
from routers.auth import get_current_user
from pydantic import BaseModel
import logging
from typing import cast

router = APIRouter(prefix="/api/user/schedules", tags=["Schedules"])
logger = logging.getLogger(__name__)

# ── Pydantic Models ──────────────────────────────────────────────────────────

class WorkScheduleModel(BaseModel):
    id: Optional[str] = None
    name: str = "Semana Laboral"
    daysEnabled: List[str] = []
    startHour: str = "09:00"
    endHour: str = "18:00"
    timezone: str = "America/Bogota"
    agentOverrides: Optional[str] = None

class StandupMeetingModel(BaseModel):
    id: Optional[str] = None
    scheduleId: Optional[str] = None      # link to a WorkSchedule
    title: str = "Daily Standup"
    description: Optional[str] = None
    location: str = "CONFERENCE_ROOM"
    cron: Optional[str] = None
    time: Optional[str] = None
    agenda: Optional[str] = None          # JSON string
    active: bool = True

# ── WorkSchedules (multi) ────────────────────────────────────────────────────

@router.get("/work", response_model=List[WorkScheduleModel])
async def list_work_schedules(user_token: dict = Depends(get_current_user)):
    """Returns ALL work schedules for the user (now supports multiple)."""
    user_id = user_token["id"]
    schedules = await db_manager.client.workschedule.find_many(
        where={"userId": user_id},
        order={"createdAt": "asc"}
    )
    return [WorkScheduleModel(**{**s.__dict__, "id": str(s.id)}) for s in schedules]

@router.post("/work", response_model=WorkScheduleModel)
async def create_work_schedule(schedule: WorkScheduleModel, user_token: dict = Depends(get_current_user)):
    """Creates a new named work schedule for the user."""
    user_id = user_token["id"]
    data = schedule.model_dump(exclude={"id"})
    data["user"] = {"connect": {"id": user_id}}
    new_s = await db_manager.client.workschedule.create(data=cast(Any, data))
    return WorkScheduleModel(**{**new_s.__dict__, "id": str(new_s.id)})

@router.patch("/work/{schedule_id}", response_model=WorkScheduleModel)
async def update_work_schedule(schedule_id: str, schedule: WorkScheduleModel, user_token: dict = Depends(get_current_user)):
    """Updates an existing work schedule."""
    user_id = user_token["id"]
    existing = await db_manager.client.workschedule.find_unique(where={"id": schedule_id})
    if not existing or str(existing.userId) != user_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    data = schedule.model_dump(exclude={"id"})
    updated = await db_manager.client.workschedule.update(where={"id": schedule_id}, data=cast(Any, data))
    return WorkScheduleModel(**{**updated.__dict__, "id": str(updated.id)})

@router.delete("/work/{schedule_id}")
async def delete_work_schedule(schedule_id: str, user_token: dict = Depends(get_current_user)):
    """Deletes a work schedule. Linked standups will have scheduleId set to null."""
    user_id = user_token["id"]
    existing = await db_manager.client.workschedule.find_unique(where={"id": schedule_id})
    if not existing or str(existing.userId) != user_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    # Unlink standups before deleting
    await db_manager.client.standupmeeting.update_many(
        where={"scheduleId": schedule_id},
        data={"scheduleId": None}  # type: ignore
    )
    await db_manager.client.workschedule.delete(where={"id": schedule_id})
    return {"status": "ok"}

# ── StandupMeetings ──────────────────────────────────────────────────────────

@router.get("/meetings", response_model=List[StandupMeetingModel])
async def list_meetings(schedule_id: Optional[str] = None, user_token: dict = Depends(get_current_user)):
    """List standups, optionally filtered by schedule."""
    user_id = user_token["id"]
    where: dict = {"userId": user_id}
    if schedule_id:
        where["scheduleId"] = schedule_id
    meetings = await db_manager.client.standupmeeting.find_many(where=where, order={"createdAt": "asc"})
    return [StandupMeetingModel(**{**m.__dict__, "id": str(m.id)}) for m in meetings]

@router.post("/meetings", response_model=StandupMeetingModel)
async def create_meeting(meeting: StandupMeetingModel, user_token: dict = Depends(get_current_user)):
    """Creates a new standup, optionally linked to a schedule."""
    user_id = user_token["id"]
    data = meeting.model_dump(exclude={"id"})
    data["user"] = {"connect": {"id": user_id}}

    # Link to schedule if provided
    schedule_id = data.pop("scheduleId", None)
    if schedule_id:
        data["schedule"] = {"connect": {"id": schedule_id}}

    new_m = await db_manager.client.standupmeeting.create(data=cast(Any, data))
    return StandupMeetingModel(**{**new_m.__dict__, "id": str(new_m.id)})

@router.patch("/meetings/{meeting_id}", response_model=StandupMeetingModel)
async def update_meeting(meeting_id: str, meeting: StandupMeetingModel, user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    existing = await db_manager.client.standupmeeting.find_unique(where={"id": meeting_id})
    if not existing or str(existing.userId) != user_id:
        raise HTTPException(status_code=404, detail="Meeting not found")

    data = meeting.model_dump(exclude={"id"})
    schedule_id = data.pop("scheduleId", None)
    if schedule_id:
        data["schedule"] = {"connect": {"id": schedule_id}}
    elif schedule_id is None and "scheduleId" in meeting.model_fields_set:
        data["scheduleId"] = None  # explicit unlink

    updated = await db_manager.client.standupmeeting.update(where={"id": meeting_id}, data=cast(Any, data))
    return StandupMeetingModel(**{**updated.__dict__, "id": str(updated.id)})

@router.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str, user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    existing = await db_manager.client.standupmeeting.find_unique(where={"id": meeting_id})
    if not existing or str(existing.userId) != user_id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await db_manager.client.standupmeeting.delete(where={"id": meeting_id})
    return {"status": "ok"}
