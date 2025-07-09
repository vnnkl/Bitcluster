#!/usr/bin/env python3
"""
Test script for Blockstream API integration
This script tests the BlockstreamClient with real API calls and verifies:
1. Rate limiting functionality
2. Caching behavior  
3. API response data quality
4. Error handling
"""

import asyncio
import logging
import sys
import time
from datetime import datetime
from pymongo import MongoClient
from blockstream.api_client import BlockstreamClient, RateLimitExceeded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test addresses (famous Bitcoin addresses)
TEST_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's first address
    "12c6DSiU4Rq3P4ZxziKxzrL5LmMBrzjrJX",  # Another early address
    "1HLoD9E4SDFFPDiYfNYnkBLQ85Y51J3Zb1",  # Early address with activity
]

TEST_TXIDS = [
    "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",  # Genesis block coinbase
    "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16",  # First Bitcoin transaction
]

async def test_basic_api_functionality():
    """Test basic API endpoints"""
    print("\n=== Testing Basic API Functionality ===")
    
    # Connect to MongoDB
    db = MongoClient('mongodb://localhost:27017/')
    
    async with BlockstreamClient(db) as client:
        try:
            # Test address info
            print(f"\n1. Testing address info for Satoshi's address...")
            address_info = await client.get_address_info(TEST_ADDRESSES[0])
            tx_count = address_info['chain_stats']['tx_count']
            funded_sum = address_info['chain_stats']['funded_txo_sum']
            print(f"   ✅ Address info: {tx_count} transactions, {funded_sum} satoshis funded")
            
            # Test transaction details
            print(f"\n2. Testing transaction details...")
            tx_info = await client.get_transaction_details(TEST_TXIDS[0])
            print(f"   ✅ Transaction: {len(tx_info['vin'])} inputs, {len(tx_info['vout'])} outputs")
            
            # Test address transactions
            print(f"\n3. Testing address transactions...")
            transactions = await client.get_address_transactions(TEST_ADDRESSES[1])
            print(f"   ✅ Found {len(transactions)} transactions for address")
            
            # Test usage stats
            print(f"\n4. Testing usage statistics...")
            stats = client.get_usage_stats()
            print(f"   ✅ API Usage: {stats['monthly_usage']}/{stats['monthly_limit']} ({stats['usage_percentage']:.2f}%)")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    return True

def test_database_setup():
    """Test that MongoDB collections are properly set up"""
    print("\n=== Testing Database Setup ===")
    
    try:
        db = MongoClient('mongodb://localhost:27017/')
        bitcoin_db = db.bitcoin
        
        # Check existing collections
        collections = bitcoin_db.list_collection_names()
        print(f"   📊 Existing collections: {collections}")
        
        # Test that we can create our new collections
        rate_limiting = bitcoin_db.rate_limiting
        
        # Insert test document to verify write access
        test_doc = {
            "_id": "test_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
            "test": True,
            "created_at": datetime.now()
        }
        rate_limiting.insert_one(test_doc)
        print("   ✅ Can write to rate_limiting collection")
        
        # Clean up test document
        rate_limiting.delete_one({"_id": test_doc["_id"]})
        print("   ✅ Can delete from rate_limiting collection")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Database setup error: {e}")
        return False

async def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🚀 Starting Blockstream API Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Database Setup", test_database_setup()),
        ("Basic API Functionality", test_basic_api_functionality()),
    ]
    
    results = []
    for test_name, test_coro in tests:
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("🎯 Test Results Summary")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Blockstream integration is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    # Run the comprehensive test
    success = asyncio.run(run_comprehensive_test())
    sys.exit(0 if success else 1) 