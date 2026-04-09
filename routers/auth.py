import json
from typing import Any, cast
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from core.auth import create_access_token, decode_access_token, get_password_hash
from core.db import db_manager
from core.logger import get_logger
from models import UserRegister, Token, UserConfig, UserProfile, UserUpdate, DEFAULT_AGENTS, DEFAULT_OFFICE_LAYOUT, DEFAULT_ROLES

logger = get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
router = APIRouter()


@router.post("/api/auth/register", response_model=Token)
async def register(user: UserRegister):
    existing = await db_manager.client.user.find_unique(where={"email": user.email})
    if existing: raise HTTPException(status_code=400, detail="Email ya registrado")
    
    new_user = await db_manager.client.user.create(
        data={
            "email": user.email,
            "passwordHash": get_password_hash(user.password),
            "name": user.name,
            "country": user.country or "CO"
        }
    )
    access_token = create_access_token(data={"sub": new_user.email, "id": str(new_user.id)})
    await ensure_user_agents(str(new_user.id))
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"id": str(new_user.id), "email": new_user.email, "name": new_user.name, "country": "CO"}
    }

@router.post("/api/auth/google", response_model=Token)
async def google_login(data: dict):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email requerido")
    
    gcp_data = {
        "gcpAccessToken": data.get("accessToken"),
        "gcpRefreshToken": data.get("refreshToken"),
        "gcpExpiresAt": data.get("expiresAt"),
        "gcpScope": data.get("scope")
    }
    update_data = {k: v for k, v in gcp_data.items() if v is not None}
    update_data["name"] = data.get("name")
    update_data["googleId"] = data.get("sub")
    update_data["country"] = data.get("country", "CO")
    google_picture = data.get("picture")

    try:
        db_user = await db_manager.client.user.find_unique(where={"email": email})
        if not db_user:
            logger.info(f"Creando nuevo usuario desde Google: {email}")
            if google_picture:
                update_data["googleAvatar"] = google_picture
                update_data["avatarType"] = "google"
            create_data = cast(Any, {"email": email, **update_data})
            db_user = await db_manager.client.user.create(data=create_data)
        else:
            logger.info(f"Actualizando tokens de conexión GCP para: {email}")
            if google_picture:
                update_data["googleAvatar"] = google_picture
                if not getattr(db_user, "avatarType", None):
                    update_data["avatarType"] = "google"
            db_user = await db_manager.client.user.update(
                where={"email": email},
                data=cast(Any, update_data)
            )
    except Exception as e:
        logger.error(f"Error crítico en DB al sincronizar Google: {e}")
        logger.warning("Probando sincronización básica sin campos GCP...")
        basic_data = {k: v for k, v in {"name": data.get("name"), "googleId": data.get("sub")}.items() if v is not None}
        db_user = await db_manager.client.user.upsert(
            where={"email": email},
            data=cast(Any, {"create": {"email": email, **basic_data}, "update": basic_data})
        )
    
    if not db_user:
        raise HTTPException(status_code=500, detail="No se pudo sincronizar el usuario de Google")
    
    access_token = create_access_token(data={"sub": db_user.email, "id": str(db_user.id)})
    await ensure_user_agents(str(db_user.id))
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {"id": str(db_user.id), "email": db_user.email, "name": db_user.name, "country": getattr(db_user, "country", "CO")}
    }

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload: raise HTTPException(status_code=401, detail="Token inválido")
    return payload

@router.post("/api/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    logger.info(f"El usuario ha cerrado sesión: {user['sub']}")
    return {"status": "success", "message": "Sesión cerrada en el backend"}

@router.get("/api/user/config", response_model=UserConfig)
async def get_user_config(user_token: dict = Depends(get_current_user)):
    user = await db_manager.client.user.find_unique(where={"id": user_token["id"]})
    if not user: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "githubToken": getattr(user, "githubToken", None),
        "notionToken": getattr(user, "notionToken", None),
        "notionWorkspaceId": getattr(user, "notionWorkspaceId", None),
        "gcpAccessToken": getattr(user, "gcpAccessToken", None),
        "gcpRefreshToken": getattr(user, "gcpRefreshToken", None),
        "gcpExpiresAt": getattr(user, "gcpExpiresAt", None),
        "gcpScope": getattr(user, "gcpScope", None)
    }

@router.patch("/api/user/config")
async def update_user_config(config: UserConfig, user_token: dict = Depends(get_current_user)):
    valid_data = {}
    if config.githubToken is not None: valid_data["githubToken"] = config.githubToken
    if config.notionToken is not None: valid_data["notionToken"] = config.notionToken
    if config.notionWorkspaceId is not None: valid_data["notionWorkspaceId"] = config.notionWorkspaceId
    if config.gcpAccessToken is not None: valid_data["gcpAccessToken"] = config.gcpAccessToken
    if config.gcpRefreshToken is not None: valid_data["gcpRefreshToken"] = config.gcpRefreshToken
    if config.gcpExpiresAt is not None: valid_data["gcpExpiresAt"] = str(config.gcpExpiresAt)
    if config.gcpScope is not None: valid_data["gcpScope"] = config.gcpScope
    if not valid_data:
        return {"status": "no_changes"}
    await db_manager.client.user.update(where={"id": user_token["id"]}, data=cast(Any, valid_data))
    return {"status": "success"}

@router.get("/api/user/profile", response_model=UserProfile)
async def get_user_profile(user_token: dict = Depends(get_current_user)):
    user = await db_manager.client.user.find_unique(where={"id": user_token["id"]})
    if not user: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "name": user.name,
        "email": user.email,
        "avatar": getattr(user, "avatar", None),
        "googleAvatar": getattr(user, "googleAvatar", None),
        "avatarType": getattr(user, "avatarType", "custom"),
        "bio": getattr(user, "bio", None),
        "role": getattr(user, "role", "Developer"),
        "language": getattr(user, "language", "es"),
        "country": getattr(user, "country", "CO")
    }

@router.patch("/api/user/profile")
async def update_user_profile(profile_data: UserUpdate, user_token: dict = Depends(get_current_user)):
    update_data = {}
    if profile_data.name is not None: update_data["name"] = profile_data.name
    if profile_data.avatar is not None: update_data["avatar"] = profile_data.avatar
    if profile_data.avatarType is not None: update_data["avatarType"] = profile_data.avatarType
    if profile_data.bio is not None: update_data["bio"] = profile_data.bio
    if profile_data.role is not None: update_data["role"] = profile_data.role
    if profile_data.language is not None: update_data["language"] = profile_data.language
    if not update_data:
        return {"status": "no_changes"}
    await db_manager.client.user.update(where={"id": user_token["id"]}, data=cast(Any, update_data))
    return {"status": "success"}

@router.get("/api/user/office-layout")
async def get_office_layout(user_token: dict = Depends(get_current_user)):
    """Returns the full office layout with desk coordinates and furniture."""
    user = await db_manager.client.user.find_unique(where={"id": user_token["id"]})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    raw = getattr(user, "officeDefaults", None)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return DEFAULT_OFFICE_LAYOUT


async def ensure_user_agents(user_id: str):
    """Garantiza que el usuario tenga sus agentes, roles y horarios por defecto (solo si no existen)."""
    from models import DEFAULT_AGENTS, DEFAULT_ROLES, DEFAULT_OFFICE_LAYOUT
    import json
    
    # 1. Enviar layout de oficina por defecto si es nuevo
    user = await db_manager.client.user.find_unique(where={"id": user_id})
    if user and not user.officeDefaults:
        await db_manager.client.user.update(
            where={"id": user_id},
            data=cast(Any, {"officeDefaults": json.dumps(DEFAULT_OFFICE_LAYOUT)})
        )

    # 2. Sincronizar Roles por defecto
    existing_roles = await db_manager.client.agentroledefinition.find_many(where={"userId": user_id})
    role_map = {r.slug: str(r.id) for r in existing_roles}
    
    for def_role in DEFAULT_ROLES:
        if def_role["slug"] not in role_map:
            role_data = {**def_role, "isDefault": True, "user": {"connect": {"id": user_id}}}
            new_role = await db_manager.client.agentroledefinition.create(data=cast(Any, role_data))
            role_map[def_role["slug"]] = str(new_role.id)

    # 3. Sincronizar Agentes por defecto
    existing_agents = await db_manager.client.agent.find_many(where={"userId": user_id})
    existing_agent_roles = {a.role for a in existing_agents}

    for def_agent in DEFAULT_AGENTS:
        if def_agent["role"] not in existing_agent_roles:
            agent_data = {k: v for k, v in def_agent.items() if k != "avatarProfile"}
            avatar_profile = def_agent.get("avatarProfile")
            
            role_def_id = role_map.get(def_agent["role"])
            
            create_data: dict = {
                "user": {"connect": {"id": user_id}}, 
                **agent_data
            }
            if role_def_id:
                create_data["roleDefinition"] = {"connect": {"id": role_def_id}}
            
            if avatar_profile is not None:
                create_data["avatarProfile"] = json.dumps(avatar_profile)
            await db_manager.client.agent.create(data=cast(Any, create_data))

    # 4. Crear UserGlobalContext base si aún no existe (V2 — High Performance)
    existing_ctx = await db_manager.client.userglobalcontext.find_unique(where={"userId": user_id})
    if not existing_ctx:
        await db_manager.client.userglobalcontext.create(
            data=cast(Any, {
                "user": {"connect": {"id": user_id}},
                "techStack": ["Next.js", "FastAPI", "Prisma", "MongoDB"],
                "codingStyle": "Clean Code, SOLID, tipado estricto. Funciones pequeñas y enfocadas.",
                "constraints": [
                    "No usar librerías sin soporte LTS activo",
                    "Todo código debe incluir manejo de errores explícito",
                    "Variables en inglés, comentarios en español"
                ],
                "documentationLinks": []
            })
        )
        logger.info(f"UserGlobalContext por defecto creado para: {user_id}")

    logger.info(f"Fábrica completa provisionada para usuario: {user_id}")