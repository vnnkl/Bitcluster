#!/usr/bin/env python3
"""
Analyze Bitcoin addresses using Blockstream API

This script fetches real Bitcoin address data from Blockstream API,
processes transactions, and stores results in the existing Bitcluster database format.

Usage:
    python3 analyze_address.py <address>
    python3 analyze_address.py 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
    python3 analyze_address.py --help
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pymongo import MongoClient

from blockstream.api_client import BlockstreamClient, RateLimitExceeded
from blockstream.data_processor import DataProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_valid_bitcoin_address(address: str) -> bool:
    """Basic validation for Bitcoin address format"""
    if not address:
        return False
    
    # Basic length and character checks
    if len(address) < 26 or len(address) > 62:
        return False
    
    # Check if it starts with valid prefixes
    valid_prefixes = ['1', '3', 'bc1', 'tb1']  # Legacy, P2SH, Bech32, Testnet
    if not any(address.startswith(prefix) for prefix in valid_prefixes):
        return False
    
    return True

async def analyze_single_address(address: str, max_transactions: int = 50) -> dict:
    """Analyze a single Bitcoin address"""
    
    if not is_valid_bitcoin_address(address):
        raise ValueError(f"Invalid Bitcoin address format: {address}")
    
    print(f"\n🔍 Analyzing Bitcoin address: {address}")
    print("=" * 60)
    
    # Connect to MongoDB
    db = MongoClient('mongodb://localhost:27017/')
    processor = DataProcessor(db)
    
    async with BlockstreamClient(db) as client:
        try:
            # Check if already processed
            existing = processor.processing_collection.find_one({"_id": address})
            if existing and existing.get("status") == "completed":
                print(f"⚠️  Address already processed at {existing.get('processed_at')}")
                node_id = existing.get("node_id")
                if node_id:
                    cluster_info = processor.get_cluster_info(node_id)
                    print(f"📊 Existing cluster info: Node ID {node_id}, {cluster_info.get('address_count', 0)} addresses")
                    return {"address": address, "status": "already_processed", "node_id": node_id}
            
            # Process the address
            print(f"📡 Fetching data from Blockstream API...")
            
            # Show current API usage
            usage_stats = client.get_usage_stats()
            print(f"📈 API Usage: {usage_stats['monthly_usage']}/{usage_stats['monthly_limit']} "
                  f"({usage_stats['usage_percentage']:.2f}%)")
            
            # Process the address
            stats = await processor.process_address(client, address, max_transactions)
            
            print(f"\n✅ Processing completed successfully!")
            print(f"   Address: {stats['address']}")
            print(f"   Node ID: {stats['node_id']}")
            print(f"   Total transactions found: {stats['total_transactions']}")
            print(f"   Processed transactions: {stats['processed_transactions']}")
            print(f"   New addresses discovered: {stats['new_addresses']}")
            
            # Show chain statistics
            chain_stats = stats.get('chain_stats', {})
            if chain_stats:
                print(f"\n📊 Address Statistics:")
                print(f"   Funded outputs: {chain_stats.get('funded_txo_count', 0)}")
                print(f"   Spent outputs: {chain_stats.get('spent_txo_count', 0)}")
                print(f"   Balance: {chain_stats.get('funded_txo_sum', 0) / 100000000:.8f} BTC")
            
            # Show discovered addresses (sample)
            discovered = stats.get('discovered_addresses', [])
            if discovered:
                print(f"\n🔗 Sample of discovered addresses:")
                for addr in discovered[:5]:  # Show first 5
                    print(f"   {addr}")
                if len(discovered) > 5:
                    print(f"   ... and {len(discovered) - 5} more")
            
            print(f"\n🌐 View in web interface: http://127.0.0.1:5001/nodes/{stats['node_id']}")
            
            return stats
            
        except RateLimitExceeded as e:
            print(f"⚠️  Rate limit exceeded: {e}")
            print(f"💡 Try again in {e.wait_time} seconds")
            return {"error": "rate_limit_exceeded", "wait_time": e.wait_time}
            
        except Exception as e:
            print(f"❌ Error analyzing address: {e}")
            logger.error(f"Error analyzing {address}: {e}", exc_info=True)
            return {"error": str(e)}

async def analyze_multiple_addresses(addresses: list, max_transactions: int = 25):
    """Analyze multiple addresses with rate limiting"""
    
    print(f"\n🔍 Analyzing {len(addresses)} Bitcoin addresses")
    print("=" * 60)
    
    results = []
    for i, address in enumerate(addresses, 1):
        print(f"\n[{i}/{len(addresses)}] Processing: {address}")
        
        try:
            result = await analyze_single_address(address, max_transactions)
            results.append(result)
            
            # Small delay between addresses to respect rate limits
            if i < len(addresses):
                print("⏳ Waiting 2 seconds before next address...")
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"❌ Failed to process {address}: {e}")
            results.append({"address": address, "error": str(e)})
    
    # Summary
    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Successfully processed: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    
    if successful:
        total_new_addresses = sum(r.get('new_addresses', 0) for r in successful)
        total_transactions = sum(r.get('processed_transactions', 0) for r in successful)
        print(f"   📈 Total new addresses discovered: {total_new_addresses}")
        print(f"   📈 Total transactions processed: {total_transactions}")
    
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Bitcoin addresses using Blockstream API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 analyze_address.py 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
  python3 analyze_address.py --max-transactions 100 12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX
  python3 analyze_address.py --file addresses.txt
  
Famous Bitcoin addresses to try:
  1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa  # Satoshi's first address
  12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX  # Early Bitcoin address
  1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1  # Address with activity
        """
    )
    
    parser.add_argument('address', nargs='?', help='Bitcoin address to analyze')
    parser.add_argument('--file', '-f', help='File containing Bitcoin addresses (one per line)')
    parser.add_argument('--max-transactions', '-t', type=int, default=50,
                       help='Maximum transactions to process per address (default: 50)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Reduce output verbosity')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Determine addresses to process
    addresses = []
    
    if args.file:
        try:
            with open(args.file, 'r') as f:
                addresses = [line.strip() for line in f if line.strip()]
            print(f"📁 Loaded {len(addresses)} addresses from {args.file}")
        except FileNotFoundError:
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
    elif args.address:
        addresses = [args.address]
    else:
        parser.print_help()
        sys.exit(1)
    
    # Validate addresses
    valid_addresses = []
    for addr in addresses:
        if is_valid_bitcoin_address(addr):
            valid_addresses.append(addr)
        else:
            print(f"⚠️  Skipping invalid address: {addr}")
    
    if not valid_addresses:
        print("❌ No valid Bitcoin addresses to process")
        sys.exit(1)
    
    print(f"🚀 Starting analysis of {len(valid_addresses)} valid addresses")
    
    # Run analysis
    try:
        if len(valid_addresses) == 1:
            result = asyncio.run(analyze_single_address(valid_addresses[0], args.max_transactions))
        else:
            result = asyncio.run(analyze_multiple_addresses(valid_addresses, args.max_transactions))
        
        print(f"\n🎉 Analysis completed! Check the web interface at http://127.0.0.1:5001")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 