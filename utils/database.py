from pymongo import AsyncMongoClient

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
            print(f"[Database] Connected → {self.db_name}.{self.collection_name}")

    async def close(self):
        """Close the MongoDB connection."""
        if self.client:
            await self.client.close()
            print("[Database] Connection closed.")
