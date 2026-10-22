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
        self.auto_slowmode = None
        self.voice_channels = None
        self.starboard = None
        self.vent = None
        self.ventban = None
        self.afk = None
        self.tags = None
        self.stock = None
        self.stock_stocks = None
        self.stock_holdings = None
        self.stock_trades = None
        self.stock_prices = None
        self.stock_activity = None
        self.stock_balances = None
        self.stock_watchlists = None
        self.stock_alerts = None

    async def connect(self):
        if not self.client:
            self.client = AsyncMongoClient(self.uri)
            db = self.client[self.db_name]
            self.collection = db[self.collection_name]
            self.tickets = db["tickets"]
            self.auto_slowmode = db["auto_slowmode"]
            self.voice_channels = db["voice_channels"]
            self.starboard = db["starboard"]
            self.vent = db["vent"]
            self.ventban = db["ventban"]
            self.afk = db["afk"]
            self.tags = db["tags"]
            self.stock = db["stock"]
            self.stock_stocks = db["stock_stocks"]
            self.stock_holdings = db["stock_holdings"]
            self.stock_trades = db["stock_trades"]
            self.stock_prices = db["stock_prices"]
            self.stock_activity = db["stock_activity"]
            self.stock_balances = db["stock_balances"]
            self.stock_watchlists = db["stock_watchlists"]
            self.stock_alerts = db["stock_alerts"]
            log.success(f"Database Connected → {self.db_name}")

    async def close(self):
        if self.client:
            await self.client.close()
            log.warning("Database Connection closed.")
