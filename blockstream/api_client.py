import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
import json
from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

class RateLimitExceeded(Exception):
    """Raised when rate limits are exceeded"""
    def __init__(self, wait_time: int):
        self.wait_time = wait_time
        super().__init__(f"Rate limit exceeded. Wait {wait_time} seconds.")

class RateLimiter:
    """Rate limiting with MongoDB persistence"""
    
    def __init__(self, db: MongoClient, monthly_limit: int = 400000):
        self.db = db
        self.monthly_limit = monthly_limit
        self.daily_limit = int(monthly_limit / 30)  # ~13,333/day
        self.hourly_limit = int(monthly_limit / (30 * 24))  # ~555/hour
        self.collection: Collection = db.bitcoin.rate_limiting
        
    def _get_current_period(self) -> str:
        """Get current month key for rate limiting"""
        return datetime.now().strftime("%Y-%m")
    
    def _get_current_day(self) -> str:
        """Get current day key for rate limiting"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_current_hour(self) -> str:
        """Get current hour key for rate limiting"""
        return datetime.now().strftime("%Y-%m-%d:%H")
    
    def check_limits(self) -> Tuple[bool, int]:
        """
        Check if we can make a request within rate limits
        Returns: (can_proceed, wait_time_seconds)
        """
        period = self._get_current_period()
        day = self._get_current_day()
        hour = self._get_current_hour()
        
        # Get current usage
        doc = self.collection.find_one({"_id": period}) or {
            "_id": period,
            "monthly_count": 0,
            "daily_counts": {},
            "hourly_counts": {},
            "last_reset": datetime.now()
        }
        
        monthly_count = doc.get("monthly_count", 0)
        daily_count = doc.get("daily_counts", {}).get(day, 0)
        hourly_count = doc.get("hourly_counts", {}).get(hour, 0)
        
        # Check monthly limit
        if monthly_count >= self.monthly_limit:
            # Wait until next month
            next_month = datetime.now().replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1, hour=0, minute=0, second=0)
            wait_time = int((next_month - datetime.now()).total_seconds())
            return False, wait_time
        
        # Check daily limit  
        if daily_count >= self.daily_limit:
            # Wait until next day
            next_day = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            wait_time = int((next_day - datetime.now()).total_seconds())
            return False, wait_time
        
        # Check hourly limit
        if hourly_count >= self.hourly_limit:
            # Wait until next hour
            next_hour = datetime.now().replace(minute=0, second=0) + timedelta(hours=1)
            wait_time = int((next_hour - datetime.now()).total_seconds())
            return False, wait_time
        
        return True, 0
    
    def record_request(self, endpoint: str, response_size: int) -> None:
        """Record a successful API request"""
        period = self._get_current_period()
        day = self._get_current_day()
        hour = self._get_current_hour()
        
        # Update counters atomically
        self.collection.update_one(
            {"_id": period},
            {
                "$inc": {
                    "monthly_count": 1,
                    f"daily_counts.{day}": 1,
                    f"hourly_counts.{hour}": 1
                },
                "$set": {
                    "last_request": datetime.now(),
                    f"endpoints.{endpoint}": {
                        "count": 1,
                        "last_used": datetime.now(),
                        "total_bytes": response_size
                    }
                }
            },
            upsert=True
        )
        
        logger.info(f"Recorded API request: {endpoint}, size: {response_size} bytes")

class CacheManager:
    """MongoDB-based caching for API responses"""
    
    def __init__(self, db: MongoClient):
        self.db = db
        self.cache_collection: Collection = db.bitcoin.blockstream_cache
        self.tx_cache_collection: Collection = db.bitcoin.transaction_cache
        
        # Create indexes for performance
        self.cache_collection.create_index("expires_at")
        self.tx_cache_collection.create_index("cached_at")
    
    def get_address_cache(self, address: str) -> Optional[Dict]:
        """Get cached address data"""
        cache_key = f"address:{address}"
        doc = self.cache_collection.find_one({
            "_id": cache_key,
            "expires_at": {"$gt": datetime.now()}
        })
        
        if doc:
            logger.debug(f"Cache hit for address: {address}")
            return doc["data"]
        
        logger.debug(f"Cache miss for address: {address}")
        return None
    
    def set_address_cache(self, address: str, data: Dict, ttl_hours: int = 24) -> None:
        """Cache address data"""
        cache_key = f"address:{address}"
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        self.cache_collection.update_one(
            {"_id": cache_key},
            {
                "$set": {
                    "data": data,
                    "cached_at": datetime.now(),
                    "expires_at": expires_at,
                    "address": address
                }
            },
            upsert=True
        )
        
        logger.debug(f"Cached address data: {address}")
    
    def get_transaction_cache(self, txid: str) -> Optional[Dict]:
        """Get cached transaction data (permanent cache)"""
        cache_key = f"txid:{txid}"
        doc = self.tx_cache_collection.find_one({"_id": cache_key})
        
        if doc:
            logger.debug(f"Cache hit for transaction: {txid}")
            return doc["data"]
        
        logger.debug(f"Cache miss for transaction: {txid}")
        return None
    
    def set_transaction_cache(self, txid: str, data: Dict) -> None:
        """Cache transaction data (permanent - transactions never change)"""
        cache_key = f"txid:{txid}"
        
        self.tx_cache_collection.update_one(
            {"_id": cache_key},
            {
                "$set": {
                    "data": data,
                    "cached_at": datetime.now(),
                    "txid": txid,
                    "permanent": True
                }
            },
            upsert=True
        )
        
        logger.debug(f"Cached transaction data: {txid}")

class BlockstreamClient:
    """Async Blockstream API client with rate limiting and caching"""
    
    def __init__(self, db: MongoClient, base_url: str = "https://blockstream.info/api"):
        self.base_url = base_url
        self.rate_limiter = RateLimiter(db)
        self.cache = CacheManager(db)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Bitcluster/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, endpoint: str) -> Dict:
        """Make rate-limited HTTP request to Blockstream API"""
        
        # Check rate limits
        can_proceed, wait_time = self.rate_limiter.check_limits()
        if not can_proceed:
            raise RateLimitExceeded(wait_time)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 429:  # Too Many Requests
                    # Exponential backoff
                    await asyncio.sleep(2 ** min(3, 1))  # 2-8 seconds
                    raise RateLimitExceeded(60)
                
                response.raise_for_status()
                data = await response.json()
                
                # Record successful request
                response_size = len(await response.text())
                self.rate_limiter.record_request(endpoint, response_size)
                
                logger.info(f"API request successful: {endpoint}")
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {endpoint}, error: {e}")
            raise
    
    async def get_address_info(self, address: str) -> Dict:
        """
        Get address information with caching
        Returns: {funded_txo_count, spent_txo_count, tx_count, etc.}
        """
        
        # Check cache first
        cached_data = self.cache.get_address_cache(address)
        if cached_data:
            return cached_data
        
        # Fetch from API
        endpoint = f"/address/{address}"
        data = await self._make_request(endpoint)
        
        # Cache the result
        self.cache.set_address_cache(address, data)
        
        return data
    
    async def get_address_transactions(self, address: str, last_seen_txid: str = None) -> List[Dict]:
        """
        Get transactions for an address
        Returns: List of transaction objects
        """
        endpoint = f"/address/{address}/txs"
        if last_seen_txid:
            endpoint += f"/{last_seen_txid}"
        
        # For transactions, we check cache for individual transactions
        # but always fetch the transaction list fresh to get latest data
        transactions = await self._make_request(endpoint)
        
        # Cache individual transactions (they never change once confirmed)
        for tx in transactions:
            if tx.get("status", {}).get("confirmed"):
                self.cache.set_transaction_cache(tx["txid"], tx)
        
        return transactions
    
    async def get_transaction_details(self, txid: str) -> Dict:
        """
        Get detailed transaction information
        Returns: Full transaction object with inputs/outputs
        """
        
        # Check cache first (transactions never change)
        cached_data = self.cache.get_transaction_cache(txid)
        if cached_data:
            return cached_data
        
        # Fetch from API
        endpoint = f"/tx/{txid}"
        data = await self._make_request(endpoint)
        
        # Cache permanently if confirmed
        if data.get("status", {}).get("confirmed"):
            self.cache.set_transaction_cache(txid, data)
        
        return data
    
    async def get_address_utxos(self, address: str) -> List[Dict]:
        """
        Get unspent transaction outputs for an address
        Returns: List of UTXO objects
        """
        endpoint = f"/address/{address}/utxo"
        return await self._make_request(endpoint)
    
    async def get_block_info(self, block_hash: str) -> Dict:
        """
        Get block information
        Returns: Block object with transaction list
        """
        endpoint = f"/block/{block_hash}"
        return await self._make_request(endpoint)
    
    async def get_latest_block_hash(self) -> str:
        """Get the hash of the latest block"""
        endpoint = "/blocks/tip/hash"
        return await self._make_request(endpoint)
    
    def get_usage_stats(self) -> Dict:
        """Get current rate limiting usage statistics"""
        period = self.rate_limiter._get_current_period()
        day = self.rate_limiter._get_current_day()
        hour = self.rate_limiter._get_current_hour()
        
        doc = self.rate_limiter.collection.find_one({"_id": period}) or {}
        
        return {
            "monthly_usage": doc.get("monthly_count", 0),
            "monthly_limit": self.rate_limiter.monthly_limit,
            "daily_usage": doc.get("daily_counts", {}).get(day, 0),
            "daily_limit": self.rate_limiter.daily_limit,
            "hourly_usage": doc.get("hourly_counts", {}).get(hour, 0),
            "hourly_limit": self.rate_limiter.hourly_limit,
            "usage_percentage": (doc.get("monthly_count", 0) / self.rate_limiter.monthly_limit) * 100
        }

# Convenience factory function
def create_blockstream_client(db: MongoClient) -> BlockstreamClient:
    """Create a new BlockstreamClient instance"""
    return BlockstreamClient(db) 