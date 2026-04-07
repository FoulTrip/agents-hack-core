# app_state.py — In-memory state shared across the FastAPI app
# agent_task_cache: maps session_id -> list of {role, task} from PM analysis
agent_task_cache: dict[str, list] = {}
