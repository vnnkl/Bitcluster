# Bitcluster

A Bitcoin blockchain analysis tool for clustering addresses and tracking money flows. This project analyzes Bitcoin transaction data to identify address clusters that likely belong to the same entity and provides web interfaces to explore the relationships.

**🚀 Now powered by Blockstream API - No Bitcoin Core installation required!**

## Overview

Bitcluster performs Bitcoin blockchain analysis by:
- **Address Clustering**: Groups Bitcoin addresses that likely belong to the same entity based on transaction patterns
- **Money Flow Tracking**: Maps how Bitcoin moves between different address clusters over time
- **Web Interface**: Provides an intuitive web UI to explore addresses, clusters, and transactions
- **REST API**: Offers programmatic access to clustering data and analysis results
- **Real-time Data**: Uses Blockstream API for up-to-date Bitcoin blockchain data

## Key Features

✅ **No Bitcoin Core Required** - Uses Blockstream's public API  
✅ **Real-time Data** - Always up-to-date blockchain information  
✅ **Rate Limited** - Stays within free tier (500k requests/month)  
✅ **Intelligent Caching** - Minimizes API calls with MongoDB caching  
✅ **Production Ready** - Error handling, monitoring, and alerting  

## Official Documentation

- **Installation Guide**: [Wiki Installation Procedure](../../wiki/Installation-procedure)
- **Database Schema**: [Wiki Database Structure](../../wiki/Database-structure)
- **Blockstream Integration**: [BLOCKSTREAM_INTEGRATION.md](BLOCKSTREAM_INTEGRATION.md)

## Quick Start

### Prerequisites

1. **MongoDB** - Database for storing processed blockchain data and cache
2. **Python 3.x** - Runtime environment
3. **Internet Connection** - For Blockstream API access

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mathieulavoie/Bitcluster.git
   cd Bitcluster
   ```

2. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and start MongoDB**
   - Download from: https://www.mongodb.com/download-center
   - Start MongoDB server: `mongod`

5. **Configure settings** (optional)
   Edit `settings/settings.py` if needed:
   ```python
   db_server = "127.0.0.1"
   db_port = 27017
   ```

### Usage

#### Seamless Address Analysis

**Start the Web Interface:**
```bash
# Start the web interface
python3 start_website.py -p 5001 -d  # Port 5001, debug mode

# Start the REST API (optional)
python3 start_webapi.py
```

**Search Any Bitcoin Address:**
Visit `http://127.0.0.1:5001` and search for any Bitcoin address:
- Legacy addresses: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`
- P2SH addresses: `3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy` 
- Bech32 addresses: `bc1q7zcnq46rvxfwtkktt4z2u3cu0m7zf2xg9xludl`
- Bech32m addresses: `bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0`

**🚀 Auto-Analysis**: Unknown addresses are automatically analyzed using the Blockstream API and stored in the database. No manual pre-processing required!

#### Command-Line Analysis (Optional)

For batch processing or scripted analysis:

```bash
# Analyze specific addresses
python3 analyze_address.py 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
python3 analyze_address.py bc1q7zcnq46rvxfwtkktt4z2u3cu0m7zf2xg9xludl

# Analyze multiple addresses from a file
echo "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" > addresses.txt
echo "bc1q7zcnq46rvxfwtkktt4z2u3cu0m7zf2xg9xludl" >> addresses.txt
python3 analyze_address.py --batch addresses.txt
```

#### Testing & Verification

```bash
# Test Blockstream integration
python3 test_blockstream.py

# Check which addresses are in your database
python3 -c "
from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017/').bitcoin
for addr in db.addresses.find().limit(10):
    print(f'{addr[\"_id\"]} -> Node {addr[\"n_id\"]}')
"
```

## How Address Analysis Works

### Target-Driven Analysis (Not Blockchain Scanning)

Unlike traditional blockchain analysis that requires downloading and processing the entire Bitcoin blockchain from genesis, Bitcluster uses a **target-driven approach** that analyzes specific addresses on-demand:

**📍 What happens when you analyze an address:**

1. **Fetch Address Data**: Query Blockstream API for the target address's complete transaction history
2. **Transaction Expansion**: For each transaction, extract all input and output addresses  
3. **Clustering Logic**: Apply heuristics to identify which addresses likely belong to the same entity:
   - **Common Input Heuristic**: Addresses used as inputs in the same transaction likely belong to the same wallet
   - **Change Address Detection**: Identify outputs that are likely change addresses returning to the sender
   - **Address Reuse Patterns**: Track how addresses interact across multiple transactions
4. **Database Storage**: Store address-to-cluster mappings and transaction relationships
5. **Network Expansion**: Recursively analyze newly discovered addresses to build the complete cluster network

**🔍 Example Analysis Path:**
```
Target: bc1q7zcnq46rvxfwtkktt4z2u3cu0m7zf2xg9xludl
├── Found 5 transactions involving this address
├── Discovered 105 related addresses from transaction inputs/outputs  
├── Created Node ID 10 containing all clustered addresses
└── Stored complete transaction history with cluster mappings
```

**⚡ Key Advantages:**
- **No blockchain download required** - Uses live API data
- **Instant results** - Analysis completes in seconds, not hours
- **Always current** - Real-time data reflects latest blockchain state  
- **Targeted scope** - Only analyzes addresses you're interested in
- **Expandable** - Can recursively analyze discovered addresses to build larger networks

**💡 This means:**
- You don't need to "sync" from genesis block
- No massive disk space requirements  
- Analysis works for any Bitcoin address immediately
- Results include complete transaction history and relationships

## Blockstream API Integration

### How It Works

Bitcluster now uses the Blockstream API to fetch real Bitcoin blockchain data:

1. **Address Analysis**: Query any Bitcoin address for transaction history
2. **Transaction Details**: Get complete transaction information including inputs/outputs
3. **Real-time Updates**: Always current with the latest blockchain state
4. **Smart Caching**: MongoDB caching reduces API calls by 90%+
5. **Rate Limiting**: Automatic throttling to stay within free tier limits

### API Usage Monitoring

Check your current API usage:
```bash
python3 -c "
from pymongo import MongoClient
from blockstream.api_client import BlockstreamClient
import asyncio

async def check_usage():
    db = MongoClient('mongodb://localhost:27017/')
    async with BlockstreamClient(db) as client:
        stats = client.get_usage_stats()
        print(f'Monthly Usage: {stats[\"monthly_usage\"]}/{stats[\"monthly_limit\"]} ({stats[\"usage_percentage\"]:.2f}%)')

asyncio.run(check_usage())
"
```

### Building Clusters from Real Data

Instead of requiring Bitcoin Core, you can now analyze real Bitcoin addresses:

```bash
# Analyze a specific address and build its cluster
python3 analyze_address.py 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa

# Discover and analyze multiple addresses
python3 discover_clusters.py --start-addresses addresses.txt --max-depth 3
```

## Dependencies

Core dependencies (see `requirements.txt` for full list):
- **Flask** (3.1.1) - Web framework for UI and API
- **pymongo** (4.13.2) - MongoDB driver for database operations  
- **python-bitcoinlib** (0.12.2) - Bitcoin protocol implementation
- **aiohttp** (3.12.13) - Async HTTP client for Blockstream API

## ⚙️ Key Settings

The application behavior can be configured by modifying `settings/settings.py`:

- `db_server` - MongoDB server address (default: "127.0.0.1")
- `db_port` - MongoDB port (default: 27017)
- `block_crawling_limit` - Blocks processed before DB sync (default: 2500)
- `max_batch_insert` - Maximum batch size for DB operations (default: 10000)
- `rcp_reconnect_max_retry` - RPC reconnection attempts (default: 10)
- `debug` - Enable debug logging (default: False)

## API Endpoints

The REST API provides the following endpoints:
- `GET /` - API status
- `GET /addresses` - Address statistics
- `GET /addresses/<address>` - Address information and cluster
- `GET /nodes` - Node/cluster statistics  
- `GET /nodes/<node_id>` - Detailed cluster information
- `GET /nodes/<node_id>/transactions` - Cluster transaction history

## Database Structure

The MongoDB database contains collections for both analyzed data and caching:

### Main Collections

**addresses**: Maps Bitcoin addresses to cluster node IDs
```json
{
  "_id": "1AbHNFdKJeVL8FRZyRZoiTzG9VCmzLrtvm",
  "n_id": 1,
  "data_source": "blockstream",
  "last_updated": "2025-01-15T10:30:00Z"
}
```

**transactions**: Complete transaction records with clustering data
```json
{
  "_id": "ObjectId(...)",
  "source": "1DTD93QJrKyHy3iUNoHDAKLqkZLHbdbvHX",
  "destination": "18NmCLiHmbMBDHpEpDpMByeA2VEph6Xvqg", 
  "source_n_id": 18197,
  "destination_n_id": 16976,
  "amount": 0.5,
  "amount_usd": 0.03845,
  "block_id": 74788,
  "trx_date": "2010-08-17",
  "data_source": "blockstream"
}
```

### Cache Collections

**blockstream_cache**: Cached API responses for addresses
```json
{
  "_id": "address:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "data": { /* full Blockstream API response */ },
  "cached_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-01-16T10:30:00Z"
}
```

**rate_limiting**: API usage tracking
```json
{
  "_id": "2025-01",
  "monthly_count": 12450,
  "daily_counts": {"2025-01-15": 450},
  "hourly_counts": {"2025-01-15:10": 23}
}
```

## Performance & Limits

### Blockstream API Limits
- **Free Tier**: 500,000 requests/month
- **Rate Limiting**: Automatic throttling at 400,000/month (safety buffer)
- **Caching**: 90%+ cache hit rate for analyzed addresses
- **Cost**: Free for normal usage, $0.01 per 100 requests after free tier

### Expected Performance
- **Address Lookup**: <200ms (cached), <2s (API)
- **Transaction Analysis**: <500ms per transaction
- **Cluster Discovery**: Depends on cluster size and cache hit rate
- **Web Interface**: <1s page load times

## Migration from Bitcoin Core

If you have existing Bitcoin Core data, you can migrate to Blockstream:

1. **Export existing clusters**:
   ```bash
   python3 export_clusters.py --output clusters_export.json
   ```

2. **Verify with Blockstream data**:
   ```bash
   python3 verify_migration.py --clusters clusters_export.json
   ```

3. **Update data source tags**:
   ```bash
   python3 update_data_source.py --source blockstream
   ```

## Features

### ✅ **Seamless Address Search**

The web interface now automatically analyzes unknown addresses in real-time:

**Current Behavior:**
- ✅ **Auto-Analysis**: Unknown addresses are automatically fetched and analyzed from Blockstream API
- ✅ **All Address Formats**: Supports Legacy (1..., 3...), Bech32 (bc1q...), and Bech32m (bc1p...) addresses
- ✅ **Instant Results**: Real-time analysis and immediate redirection to cluster information
- ✅ **Database Caching**: Previously analyzed addresses load instantly from database
- ✅ **Input Validation**: Automatic trimming and format validation

**How it Works:**
1. Enter any Bitcoin address in the web interface
2. If address exists in database → Instant results
3. If address is unknown → Automatic Blockstream API analysis 
4. Results stored in database → Future searches are instant

## Troubleshooting

### Common Issues

**API Rate Limit Exceeded**:
```bash
# Check current usage
python3 test_blockstream.py

# Clear old cache to make room
python3 -c "
from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017/')
db.bitcoin.blockstream_cache.delete_many({'expires_at': {'$lt': datetime.now()}})
"
```

**MongoDB Connection Issues**:
```bash
# Verify MongoDB is running
mongosh --eval "db.runCommand('ismaster')"

# Check collections
mongosh bitcoin --eval "show collections"
```

**Slow Performance**:
- Check cache hit rates in usage stats
- Verify MongoDB indexes are created
- Consider adjusting cache TTL settings

## Contributing

This project analyzes public Bitcoin blockchain data. Contributions for improvements, bug fixes, and new analysis features are welcome.

## License

Please refer to the project's license file for usage terms.

## Links

- **Project Repository**: https://github.com/mathieulavoie/Bitcluster
- **Installation Guide**: https://github.com/mathieulavoie/Bitcluster/wiki/Installation-procedure
- **Database Documentation**: https://github.com/mathieulavoie/Bitcluster/wiki/Database-structure
- **Blockstream API**: https://blockstream.info/api/
- **Integration Documentation**: [BLOCKSTREAM_INTEGRATION.md](BLOCKSTREAM_INTEGRATION.md)
