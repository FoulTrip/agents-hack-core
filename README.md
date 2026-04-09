# TripKode Agents - Enterprise Edition

**TripKode Agents** no es solo un ecosistema agéntico de desarrollo; es una plataforma de **Simulación de Organizaciones Autónomas**. Permite desplegar fuerzas de trabajo digitales completas, automatizar jerarquías empresariales y visualizar flujos de trabajo en un entorno virtual 3D en tiempo real.

---

## Características Principales (Enterprise Grade)

### 1. Gobernanza Financiera (GCP Billing Integration)
*   **Official Metrics SDK**: Integración directa con `google-cloud-monitoring` para obtener consumo real de tokens desde la infraestructura de Vertex AI.
*   **Cost Attribution via Labels**: Cada petición de agente inyecta etiquetas (`user_id`, `session_id`) en GCP para una auditoría financiera exacta por cliente y proyecto.
*   **Budget Guardian (Active Enforcement)**: Bloqueo proactivo del pipeline. Si el gasto diario acumulado del usuario supera su límite configurado en MongoDB, el sistema detiene todas las ejecuciones de IA.
*   **Reconciliación Nocturna**: Endpoint `/api/recon/billing` diseñado para **Google Cloud Scheduler**. Sincroniza cada noche los balances locales con la facturación real de Google para una precisión contable del 100%.

### 2. Human-in-the-Loop (HITL)
*   **Checkpoint de Arquitectura**: El orquestador pausa automáticamente la ejecución tras la fase de diseño técnico.
*   **Aprobación Manual**: Requiere intervención explícita del Administrador (vía API o Dashboard) para proceder con el desarrollo, evitando alucinaciones o arquitecturas costosas no deseadas.

### 3. Seguridad y Privacidad (Zero-Trust)
*   **PII Sanitizer Middleware**: Detección y enmascaramiento automático de información sensible (IPs, Tokens, Emails, Secret Keys) antes de enviar prompts a los modelos públicos de Vertex AI.
*   **Secured Logs**: Los logs de actividad en la base de datos local también se guardan sanitizados para mantener un entorno de "Zero Privacy Leak".

### 4. Colaboración y HUD 3D
*   **Presencia Multi-usuario**: Visualización en tiempo real de qué administradores están conectados en la oficina virtual.
*   **Claw3D SDK**: Sincronización de agentes y humanos en el entorno 3D mediante WebSockets persistentes gestionados por `SessionManager`.

---

## Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Orquestación** | Google ADK (v1.27.x) |
| **Modelos de IA** | Gemini 1.5 Pro/Flash, Claude 3.5 Sonnet (Vertex AI) |
| **Backend** | FastAPI (Python 3.11+) |
| **Persistencia** | MongoDB (con Prisma ORM) |
| **Nube** | Google Cloud Run, Cloud Scheduler, BigQuery Export |
| **Simulación** | Claw3D Virtual Office |

---

## Guía de Inicio Rápido

1.  **Configurar Variables de Env**:
    ```bash
    GOOGLE_CLOUD_PROJECT=tu-proyecto-id
    DATABASE_URL=mongodb+srv://...
    CLOUD_SCHEDULER_SECRET=tu_secreto_para_recon
    ```
2.  **Lanzar el Servidor**:
    ```bash
    # Usar venv
    uvicorn server:app --reload
    ```
3.  **Probar con el Prompt Enterprise**:
    Utiliza el archivo `SAMPLE_CLIENT_PROMPT.txt` en la raíz para validar todas las capas (Gobernanza, PII, HITL y Desarrollo).

---

## Endpoints Críticos (v3)

*   `POST /api/generate`: Inicia el pipeline agéntico con auditoría de costos.
*   `POST /api/approve/{id}`: Libera una fase detenida por el sistema HITL.
*   `POST /api/recon/billing`: Endpoint de reconciliación para Cloud Scheduler (Bearer Auth).
*   `GET  /api/analytics/gcloud`: Reporte financiero en tiempo real desde Metrics SDK.
*   `WS   /ws/{id}?userId=...`: Canal de comunicación para presencia y pipeline logs.

---
*Desarrollado por el equipo de TripKode Agentic Systems.*