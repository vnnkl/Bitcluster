import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple
from pymongo import MongoClient
from pymongo.collection import Collection
from blockstream.api_client import BlockstreamClient

logger = logging.getLogger(__name__)

class DataProcessor:
    """Processes Blockstream API data and converts to Bitcluster database format"""
    
    def __init__(self, db: MongoClient):
        self.db = db
        self.addresses_collection: Collection = db.bitcoin.addresses
        self.transactions_collection: Collection = db.bitcoin.transactions
        self.processing_collection: Collection = db.bitcoin.processing_status
        
        # Create indexes for performance
        self._create_indexes()
        
        # Node ID counter for new clusters
        self.next_node_id = self._get_next_node_id()
        
    def _create_indexes(self):
        """Create necessary indexes for performance"""
        try:
            self.addresses_collection.create_index("n_id")
            self.addresses_collection.create_index("data_source")
            self.addresses_collection.create_index("last_updated")
            
            self.transactions_collection.create_index([("source", 1), ("destination", 1)])
            self.transactions_collection.create_index("source_n_id")
            self.transactions_collection.create_index("destination_n_id")
            self.transactions_collection.create_index("data_source")
            
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    def _get_next_node_id(self) -> int:
        """Get the next available node ID"""
        try:
            # Find the highest existing node ID
            max_doc = self.addresses_collection.find().sort("n_id", -1).limit(1)
            max_list = list(max_doc)
            if max_list:
                return max_list[0]["n_id"] + 1
            else:
                return 1
        except Exception:
            return 1
    
    def _get_or_create_node_id(self, address: str) -> int:
        """Get existing node ID for address or create new one"""
        existing = self.addresses_collection.find_one({"_id": address})
        if existing:
            return existing["n_id"]
        
        # Create new node ID
        node_id = self.next_node_id
        self.next_node_id += 1
        
        # Store in database
        self.addresses_collection.update_one(
            {"_id": address},
            {
                "$set": {
                    "n_id": node_id,
                    "data_source": "blockstream",
                    "last_updated": datetime.now()
                }
            },
            upsert=True
        )
        
        logger.info(f"Created new node ID {node_id} for address {address}")
        return node_id
    
    def _parse_blockstream_transaction(self, tx_data: Dict) -> List[Dict]:
        """
        Parse a Blockstream transaction into our database format
        Returns list of transaction records (one per input-output pair)
        """
        transactions = []
        tx_id = tx_data["txid"]
        
        # Get block info
        status = tx_data.get("status", {})
        block_height = status.get("block_height")
        block_time = status.get("block_time")
        
        # Convert timestamp to date string
        if block_time:
            tx_date = datetime.fromtimestamp(block_time).strftime("%Y-%m-%d")
        else:
            tx_date = datetime.now().strftime("%Y-%m-%d")  # Unconfirmed
        
        # Process each input-output combination
        inputs = tx_data.get("vin", [])
        outputs = tx_data.get("vout", [])
        
        for input_data in inputs:
            # Skip coinbase transactions (mining rewards)
            if "coinbase" in input_data:
                continue
                
            input_addr = input_data.get("prevout", {}).get("scriptpubkey_address")
            if not input_addr:
                continue
                
            input_value = input_data.get("prevout", {}).get("value", 0)
            
            for output_data in outputs:
                output_addr = output_data.get("scriptpubkey_address")
                if not output_addr or output_addr == input_addr:
                    continue  # Skip change back to same address
                    
                output_value = output_data.get("value", 0)
                
                # Get or create node IDs
                source_node_id = self._get_or_create_node_id(input_addr)
                dest_node_id = self._get_or_create_node_id(output_addr)
                
                # Calculate proportional amount (simplified)
                total_input_value = sum(inp.get("prevout", {}).get("value", 0) 
                                      for inp in inputs if "prevout" in inp)
                
                if total_input_value > 0:
                    proportion = input_value / total_input_value
                    amount_satoshis = int(output_value * proportion)
                    amount_btc = amount_satoshis / 100000000  # Convert to BTC
                else:
                    amount_btc = 0
                
                transaction_record = {
                    "txid": tx_id,
                    "source": input_addr,
                    "destination": output_addr,
                    "source_n_id": source_node_id,
                    "destination_n_id": dest_node_id,
                    "amount": amount_btc,
                    "amount_usd": amount_btc * 50000,  # Rough USD estimate, should be updated with real prices
                    "block_id": block_height,
                    "trx_date": tx_date,
                    "data_source": "blockstream",
                    "processed_at": datetime.now()
                }
                
                transactions.append(transaction_record)
        
        return transactions
    
    async def process_address(self, client: BlockstreamClient, address: str, 
                            max_transactions: int = 50) -> Dict:
        """
        Process a single address: fetch data and store in database
        Returns processing statistics
        """
        logger.info(f"Processing address: {address}")
        
        try:
            # Get address information
            addr_info = await client.get_address_info(address)
            
            # Get or create node ID for this address
            node_id = self._get_or_create_node_id(address)
            
            # Get recent transactions
            transactions = await client.get_address_transactions(address)
            
            # Limit number of transactions for initial processing
            transactions = transactions[:max_transactions]
            
            processed_txs = 0
            new_addresses = set()
            
            # Process each transaction
            for tx_data in transactions:
                try:
                    # Check if we already processed this transaction
                    existing = self.transactions_collection.find_one({
                        "txid": tx_data["txid"], 
                        "data_source": "blockstream"
                    })
                    
                    if existing:
                        continue  # Skip already processed
                    
                    # Parse transaction
                    tx_records = self._parse_blockstream_transaction(tx_data)
                    
                    # Store in database
                    if tx_records:
                        self.transactions_collection.insert_many(tx_records)
                        processed_txs += 1
                        
                        # Collect new addresses for potential further processing
                        for record in tx_records:
                            new_addresses.add(record["source"])
                            new_addresses.add(record["destination"])
                
                except Exception as e:
                    logger.error(f"Error processing transaction {tx_data.get('txid', 'unknown')}: {e}")
            
            # Update processing status
            self.processing_collection.update_one(
                {"_id": address},
                {
                    "$set": {
                        "processed_at": datetime.now(),
                        "node_id": node_id,
                        "tx_count": len(transactions),
                        "processed_tx_count": processed_txs,
                        "status": "completed"
                    }
                },
                upsert=True
            )
            
            stats = {
                "address": address,
                "node_id": node_id,
                "total_transactions": len(transactions),
                "processed_transactions": processed_txs,
                "new_addresses": len(new_addresses),
                "chain_stats": addr_info.get("chain_stats", {}),
                "discovered_addresses": list(new_addresses)
            }
            
            logger.info(f"Completed processing {address}: {processed_txs} transactions, {len(new_addresses)} new addresses")
            return stats
            
        except Exception as e:
            logger.error(f"Error processing address {address}: {e}")
            
            # Mark as failed
            self.processing_collection.update_one(
                {"_id": address},
                {
                    "$set": {
                        "processed_at": datetime.now(),
                        "status": "failed",
                        "error": str(e)
                    }
                },
                upsert=True
            )
            
            raise
    
    async def discover_cluster(self, client: BlockstreamClient, start_address: str, 
                             max_depth: int = 2, max_addresses: int = 100) -> Dict:
        """
        Discover a cluster starting from an address by following transaction links
        """
        logger.info(f"Starting cluster discovery from {start_address}, max_depth={max_depth}")
        
        discovered_addresses = set([start_address])
        processing_queue = [(start_address, 0)]  # (address, depth)
        processed_addresses = set()
        total_stats = {
            "start_address": start_address,
            "total_addresses": 0,
            "total_transactions": 0,
            "depth_reached": 0,
            "processing_time": 0
        }
        
        start_time = datetime.now()
        
        while processing_queue and len(discovered_addresses) < max_addresses:
            address, depth = processing_queue.pop(0)
            
            if address in processed_addresses or depth > max_depth:
                continue
                
            try:
                # Process this address
                stats = await self.process_address(client, address, max_transactions=25)
                processed_addresses.add(address)
                
                total_stats["total_addresses"] += 1
                total_stats["total_transactions"] += stats["processed_transactions"]
                total_stats["depth_reached"] = max(total_stats["depth_reached"], depth)
                
                # Add newly discovered addresses to queue for next depth level
                if depth < max_depth:
                    for new_addr in stats.get("discovered_addresses", []):
                        if new_addr not in discovered_addresses and len(discovered_addresses) < max_addresses:
                            discovered_addresses.add(new_addr)
                            processing_queue.append((new_addr, depth + 1))
                
                logger.info(f"Processed {address} at depth {depth}, "
                           f"discovered {len(discovered_addresses)} total addresses")
                
                # Rate limiting: small delay between addresses
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing {address} at depth {depth}: {e}")
                processed_addresses.add(address)  # Mark as processed to avoid retry
        
        total_stats["processing_time"] = (datetime.now() - start_time).total_seconds()
        total_stats["discovered_addresses"] = list(discovered_addresses)
        
        logger.info(f"Cluster discovery completed: {total_stats['total_addresses']} addresses, "
                   f"{total_stats['total_transactions']} transactions in {total_stats['processing_time']:.1f}s")
        
        return total_stats
    
    def get_cluster_info(self, node_id: int) -> Dict:
        """Get information about a cluster (compatible with existing web interface)"""
        # Get all addresses in this cluster
        addresses = list(self.addresses_collection.find({"n_id": node_id}))
        
        if not addresses:
            return {"error": "Node not found"}
        
        # Get all transactions involving this cluster
        transactions = list(self.transactions_collection.find({
            "$or": [
                {"source_n_id": node_id},
                {"destination_n_id": node_id}
            ]
        }))
        
        # Calculate statistics
        total_received = sum(tx["amount"] for tx in transactions if tx["destination_n_id"] == node_id)
        total_sent = sum(tx["amount"] for tx in transactions if tx["source_n_id"] == node_id)
        
        return {
            "node_id": node_id,
            "addresses": [addr["_id"] for addr in addresses],
            "address_count": len(addresses),
            "transaction_count": len(transactions),
            "total_received": total_received,
            "total_sent": total_sent,
            "balance": total_received - total_sent,
            "transactions": transactions[:50],  # Limit for web display
            "data_source": "blockstream"
        } 