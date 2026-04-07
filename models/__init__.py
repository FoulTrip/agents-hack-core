from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# --- User Auth Models ---

class UserRegister(BaseModel):
    email: str
    password: str
    name: str
    country: Optional[str] = "CO"

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    avatarType: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[str] = None
    language: Optional[str] = None

class UserModel(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: Optional[str] = "Developer"
    language: str = "es"
    country: str = "CO"
    preferredModel: str = "gemini-flash"
    githubToken: Optional[str] = None
    notionToken: Optional[str] = None
    notionWorkspaceId: Optional[str] = None
    avatar: Optional[str] = None
    googleAvatar: Optional[str] = None
    officeTheme: str = "modern"

class UserConfig(BaseModel):
    githubToken: Optional[str] = None
    notionToken: Optional[str] = None
    notionWorkspaceId: Optional[str] = None
    language: Optional[str] = "es"
    country: Optional[str] = "CO"
    preferredModel: Optional[str] = "gemini-flash"
    # Vertex Sync
    gcpAccessToken: Optional[str] = None
    gcpRefreshToken: Optional[str] = None
    gcpExpiresAt: Optional[Any] = None
    gcpScope: Optional[str] = None

class UserProfile(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    googleAvatar: Optional[str] = None
    avatarType: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    preferredModel: Optional[str] = None

class AgentRoleDefinitionModel(BaseModel):
    id: Optional[str] = None
    userId: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = "Cpu"
    color: Optional[str] = "#6366F1"
    systemPrompt: Optional[str] = None
    
    # Custom Persona defaults
    personality: Optional[str] = None
    context: Optional[str] = None
    guidelines: Optional[str] = None
    boundaries: Optional[str] = None
    instructions: Optional[str] = None
    
    isDefault: bool = False
    createdAt: Optional[Any] = None

# --- Agent Models ---

class AgentModel(BaseModel):
    id: Optional[str] = None
    userId: Optional[str] = None
    name: str
    role: str
    roleDefinitionId: Optional[str] = None
    icon: str
    color: str
    description: Optional[str] = None
    model: str = "gemini-3-flash-preview"
    avatarUrl: Optional[str] = None
    
    # Claw3D Identity
    vibe: Optional[str] = "Sharp and helpful"
    emoji: Optional[str] = "🤖"
    
    # Claw3D Soul & Persona
    personality: Optional[str] = None
    context: Optional[str] = None
    guidelines: Optional[str] = None
    boundaries: Optional[str] = "No realizar acciones destructivas."
    operatingInstructions: Optional[str] = "Pasos claros y lógicos."
    
    # OCEAN (0-1)
    openness: float = 0.8
    conscientiousness: float = 0.9
    extraversion: float = 0.6
    agreeableness: float = 0.7
    neuroticism: float = 0.2
    
    # Claw3D Office Social & Appearance (Optional fields for Pydantic to avoid ValidationErrors on null DB)
    avatarStyle: Optional[str] = "pixel"
    avatarProfile: Optional[Dict[str, str]] = None
    status: Optional[str] = "idle"
    officeDesk: Optional[str] = None
    officeWing: Optional[str] = "Core"
    officeFloor: Optional[int] = 1
    socialTone: Optional[str] = "Professional"
    standupBehavior: Optional[str] = "Participant"
    computerType: Optional[str] = "high-end-pc"

    # Tools & Connectors
    tools: List[str] = []
    connectors: List[str] = []
    
    # LLM Overrides
    temperature: float = 0.7
    maxTokens: int = 4096

    order: int
    active: bool = True
    currentTask: Optional[str] = None


# --- Office Layout ---
# Stored in User.officeDefaults as JSON on registration.
# Each desk slot has x/y grid coords, wing, floor, and furniture items.

DEFAULT_OFFICE_LAYOUT = {
    "version": 1,
    "theme": "modern",
    "desks": [
        {"id": "DESK-A1", "label": "Advisor Desk",   "wing": "Executive", "floor": 1,
         "x": 2,  "y": 2,  "rotation": 0, "occupiedBy": "requirements_agent",
         "furniture": ["desk", "chairDesk", "computerScreen", "lampRoundFloor", "plantSmall1"]},
        {"id": "DESK-T1", "label": "Architect Desk", "wing": "Tech",      "floor": 1,
         "x": 6,  "y": 2,  "rotation": 0, "occupiedBy": "architecture_agent",
         "furniture": ["deskCorner", "chairDesk", "computerScreen"]},
        {"id": "DESK-D1", "label": "Developer Desk", "wing": "Tech",      "floor": 1,
         "x": 6,  "y": 5,  "rotation": 0, "occupiedBy": "development_agent",
         "furniture": ["desk", "chairDesk", "computerScreen", "tableCoffee"]},
        {"id": "DESK-Q1", "label": "QA Desk",        "wing": "Tech",      "floor": 1,
         "x": 10, "y": 5,  "rotation": 0, "occupiedBy": "qa_agent",
         "furniture": ["desk", "chairDesk", "computerScreen"]},
        {"id": "DESK-S1", "label": "Docs Desk",      "wing": "Support",   "floor": 1,
         "x": 2,  "y": 8,  "rotation": 0, "occupiedBy": "documentation_agent",
         "furniture": ["desk", "chairDesk", "computerScreen", "bookcaseClosed"]},
        {"id": "DESK-I1", "label": "DevOps Desk",    "wing": "Core",      "floor": 1,
         "x": 10, "y": 2,  "rotation": 0, "occupiedBy": "devops_agent",
         "furniture": ["deskCorner", "chairDesk", "computerScreen", "lampRoundFloor"]},
        {"id": "DESK-X1", "label": "Open Desk 1",    "wing": "Open",      "floor": 1,
         "x": 14, "y": 2,  "rotation": 0, "occupiedBy": None,
         "furniture": ["desk", "chairDesk"]},
        {"id": "DESK-X2", "label": "Open Desk 2",    "wing": "Open",      "floor": 1,
         "x": 14, "y": 5,  "rotation": 0, "occupiedBy": None,
         "furniture": ["desk", "chairDesk"]},
    ],
    "sharedSpaces": [
        {"id": "meeting-room-1", "label": "Sala de Reuniones",   "x": 14, "y": 8,  "type": "meeting",
         "furniture": ["table", "chairModernCushion", "loungeSofa"]},
        {"id": "kitchen-1",      "label": "Cocina / Break Room", "x": 2,  "y": 14, "type": "kitchen",
         "furniture": ["kitchenCoffeeMachine", "kitchenFridgeSmall", "kitchenCabinet"]},
        {"id": "lounge-1",       "label": "Lounge",              "x": 10, "y": 14, "type": "lounge",
         "furniture": ["loungeSofa", "loungeDesignChair", "tableCoffee", "pottedPlant"]},
        {"id": "ping-pong-1",    "label": "Ping Pong Area",      "x": 14, "y": 14, "type": "game",
         "furniture": ["PingPongTable"]},
    ]
}


DEFAULT_AGENTS = [
    {
        "name": "Advisor Agent", "role": "requirements_agent", "icon": "ShieldCheck", "color": "#10B981", "order": 1, 
        "description": "Analista de requerimientos", "model": "gemini-3-flash-preview", "connectors": ["notion"],
        "emoji": "🧠", "vibe": "Profesional agudo", "status": "sitting",
        "avatarStyle": "3d", "officeDesk": "DESK-A1", "officeWing": "Executive", "officeFloor": 1, 
        "socialTone": "Professional", "standupBehavior": "Leader", "computerType": "macbook",
        "avatarProfile": {"skinColor": "#E0AC69", "hairStyle": "bob", "hairColor": "#2C1B18", "shirtColor": "#10B981", "pantsColor": "#1F2937", "shoeColor": "#111827"}
    },
    {
        "name": "Architect Agent", "role": "architecture_agent", "icon": "Layers", "color": "#3B82F6", "order": 2, 
        "description": "Diseño de infraestructura", "model": "gemini-3-flash-preview", "connectors": ["notion"],
        "emoji": "📐", "vibe": "Arquitecto visionario", "status": "working",
        "avatarStyle": "3d", "officeDesk": "DESK-T1", "officeWing": "Tech", "officeFloor": 1, 
        "socialTone": "Formal", "standupBehavior": "Participant", "computerType": "workstation",
        "avatarProfile": {"skinColor": "#FFDBAC", "hairStyle": "buzz", "hairColor": "#4B2C20", "shirtColor": "#3B82F6", "pantsColor": "#374151", "shoeColor": "#111827"}
    },
    {
        "name": "Developer Agent", "role": "development_agent", "icon": "Code2", "color": "#F59E0B", "order": 3, 
        "description": "Escritura de código", "model": "gemini-3-flash-preview", "connectors": ["github", "notion"],
        "emoji": "💻", "vibe": "Codificador implacable", "status": "working",
        "avatarStyle": "pixel", "officeDesk": "DESK-D1", "officeWing": "Tech", "officeFloor": 1, 
        "socialTone": "Casual", "standupBehavior": "Participant", "computerType": "high-end-pc",
        "avatarProfile": {"skinColor": "#F1C27D", "hairStyle": "messy", "hairColor": "#000000", "shirtColor": "#F59E0B", "pantsColor": "#1F2937", "shoeColor": "#000000"}
    },
    {
        "name": "QA Agent", "role": "qa_agent", "icon": "TestTube2", "color": "#8B5CF6", "order": 4, 
        "description": "Validación y pruebas", "model": "gemini-3-flash-preview", "connectors": ["github"],
        "emoji": "🧪", "vibe": "Ojo de lince", "status": "sitting",
        "avatarStyle": "pixel", "officeDesk": "DESK-Q1", "officeWing": "Tech", "officeFloor": 1, 
        "socialTone": "Professional", "standupBehavior": "Participant", "computerType": "pc",
        "avatarProfile": {"skinColor": "#FFDBAC", "hairStyle": "long", "hairColor": "#7B3F00", "shirtColor": "#8B5CF6", "pantsColor": "#4B5563", "shoeColor": "#1F2937"}
    },
    {
        "name": "Docs Agent", "role": "documentation_agent", "icon": "BookOpen", "color": "#06B6D4", "order": 5, 
        "description": "Documentación técnica", "model": "gemini-3-flash-preview", "connectors": ["github"],
        "emoji": "📚", "vibe": "Narrador técnico", "status": "idle",
        "avatarStyle": "emoji", "officeDesk": "DESK-S1", "officeWing": "Content", "officeFloor": 1, 
        "socialTone": "Casual", "standupBehavior": "Participant", "computerType": "laptop",
        "avatarProfile": {"skinColor": "#E0AC69", "hairStyle": "medium", "hairColor": "#3D2314", "shirtColor": "#06B6D4", "pantsColor": "#374151", "shoeColor": "#111827"}
    },
    {
        "name": "DevOps Agent", "role": "devops_agent", "icon": "Server", "color": "#EC4899", "order": 6, 
        "description": "Infraestructura", "model": "gemini-3-flash-preview", "connectors": ["github", "google-cloud"],
        "emoji": "🚀", "vibe": "Maestro de nubes", "status": "working",
        "avatarStyle": "3d", "officeDesk": "DESK-I1", "officeWing": "Core", "officeFloor": 1, 
        "socialTone": "Formal", "standupBehavior": "Participant", "computerType": "workstation",
        "avatarProfile": {"skinColor": "#FFDBAC", "hairStyle": "crew", "hairColor": "#000000", "shirtColor": "#EC4899", "pantsColor": "#1F2937", "shoeColor": "#111827"}
    }
]

DEFAULT_ROLES = [
    {
        "name": "Advisor Agent", "slug": "requirements_agent", "icon": "ShieldCheck", "color": "#10B981", 
        "description": "Expert in business analysis and requirements gathering.",
        "personality": "Professional, sharp, and helpful.",
        "guidelines": "Ensure all requirements are clear and documented.",
        "systemPrompt": "Eres un Advisor / Business Analyst experto. Tu objetivo es desglosar requerimientos complejos en tareas accionables, identificar riesgos de negocio y asegurar que la visión del producto sea técnicamente viable."
    },
    {
        "name": "Software Architect", "slug": "architecture_agent", "icon": "Layers", "color": "#3B82F6",
        "description": "Expert in system design and design patterns.",
        "personality": "Visionary, structured and methodology-driven.",
        "guidelines": "Promote clean architecture and solid principles.",
        "systemPrompt": "Eres un Arquitecto de Software visionario. Tu prioridad es el diseño de infraestructuras escalables, la elección de stacks tecnológicos modernos y la implementación de patrones de diseño que garanticen la mantenibilidad a largo plazo."
    },
    {
        "name": "Full Stack Developer", "slug": "development_agent", "icon": "Code2", "color": "#F59E0B",
        "description": "Expert in writing clean, scalable code.",
        "personality": "Pragmatic, efficient and detail-oriented.",
        "guidelines": "Focus on readability and performance.",
        "systemPrompt": "Eres un Full Stack Developer Senior. Tu misión es transformar diseños arquitectónicos en código limpio, eficiente y bien testeado. Dominas tanto el backend como el frontend y priorizas la experiencia de usuario final."
    },
    {
        "name": "QA Engineer", "slug": "qa_agent", "icon": "TestTube2", "color": "#8B5CF6",
        "description": "Expert in testing and quality assurance.",
        "personality": "Meticulous, thorough and observant.",
        "guidelines": "Identify bugs and edge cases before deployment.",
        "systemPrompt": "Eres un Ingeniero de QA implacable. Tu objetivo es encontrar fallos antes que el usuario. Diseñas planes de pruebas integrales, automatizas testing y validas que cada funcionalidad cumpla con los estándares de calidad más exigentes."
    },
    {
        "name": "Technical Writer", "slug": "documentation_agent", "icon": "BookOpen", "color": "#06B6D4",
        "description": "Expert in technical documentation and user guides.",
        "personality": "Clear, concise and explanatory.",
        "guidelines": "Maintain up-to-date and accessible documentation.",
        "systemPrompt": "Eres un Technical Writer experto. Tu tarea es hacer que lo complejo parezca simple. Generas documentación técnica impecable, guías de usuario claras y mantienes actualizado el conocimiento del proyecto para todo el equipo."
    },
    {
        "name": "DevOps Engineer", "slug": "devops_agent", "icon": "Server", "color": "#EC4899", 
        "description": "Expert in cloud infrastructure and CI/CD pipelines.",
        "personality": "Analytic, precise and focused on reliability.",
        "guidelines": "Prioritize infrastructure as code. Ensure security by default.",
        "systemPrompt": "Eres un Ingeniero DevOps de élite. Tu foco es la automatización total, la estabilidad de los entornos de producción y la seguridad de la nube. Orquestas pipelines de CI/CD y aseguras que el despliegue sea continuo y fiable."
    }
]

class PipelineStatus(BaseModel):
    session_id: str
    title: str
    status: str
    current_phase: Optional[int] = None
    completed_phases: list = []
    logs: list = []
    created_at: str
    updated_at: str

class ActivityReport(BaseModel):
    sessionId: str
    agentName: str
    agentRole: str
    action: str
    message: Optional[str] = None
    thought: Optional[str] = None