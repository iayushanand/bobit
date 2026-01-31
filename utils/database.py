from pymongo import AsyncMongoClient
from utils.logger import Logger

log = Logger("Database")

class Database:
    def __init__(self, uri: str):
        self.uri = uri
        self.db_name = "bitbotdb"
        self.collection_name = "database"

        self.client: AsyncMongoClient | None = None
        self.collection = None
        self.tickets = None

    async def connect(self):
        if not self.client:
            self.client = AsyncMongoClient(self.uri)
            db = self.client[self.db_name]
            self.collection = db[self.collection_name]
            self.tickets = db["tickets"]
            log.success(f"Database Connected → {self.db_name}")

    async def close(self):
        if self.client:
            await self.client.close()
            log.success("Database Connection closed.")

