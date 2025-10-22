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

    async def connect(self):
        """Connect to MongoDB and store the collection."""
        if not self.client:
            self.client = AsyncMongoClient(self.uri)
            db = self.client[self.db_name]
            self.collection = db[self.collection_name]
            log.success(f"Database Connected → {self.db_name}.{self.collection_name}")

    async def close(self):
        """Close the MongoDB connection."""
        if self.client:
            await self.client.close()
            log.success("Database Connection closed.")
