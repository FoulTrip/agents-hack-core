# core/db.py
import asyncio
from prisma import Prisma
from core.logger import get_logger

logger = get_logger(__name__)

class Database:
    _instance = None
    _client: Prisma | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._client = Prisma()
        return cls._instance

    @property
    def client(self) -> Prisma:
        if self._client is None:
            self._client = Prisma()
        return self._client

    async def connect(self):
        client = self.client
        if not client.is_connected():
            logger.info("Conectando a MongoDB mediante Prisma...")
            await client.connect()
            logger.info("Conexión a MongoDB establecida.")

    async def disconnect(self):
        if self._client is not None and self._client.is_connected():
            logger.info("Desconectando de MongoDB...")
            await self._client.disconnect()

db_manager = Database()
