# Bitcluster

A Bitcoin blockchain analysis tool for clustering addresses and tracking money flows. This project analyzes Bitcoin transaction data to identify address clusters that likely belong to the same entity and provides web interfaces to explore the relationships.

## Overview

Bitcluster performs Bitcoin blockchain analysis by:
- **Address Clustering**: Groups Bitcoin addresses that likely belong to the same entity based on transaction patterns
- **Money Flow Tracking**: Maps how Bitcoin moves between different address clusters over time
- **Web Interface**: Provides an intuitive web UI to explore addresses, clusters, and transactions
- **REST API**: Offers programmatic access to clustering data and analysis results

## Official Documentation

- **Installation Guide**: [Wiki Installation Procedure](../../wiki/Installation-procedure)
- **Database Schema**: [Wiki Database Structure](../../wiki/Database-structure)
- **Project Website**: http://www.bit-cluster.com

## Quick Start

### Prerequisites

1. **MongoDB** - Database for storing processed blockchain data
2. **Python 3.x** - Runtime environment
3. **Bitcoin Core** (optional) - For building database from scratch

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

5. **Get the database** (Choose one option)
   
   **Option A: Download pre-built database (Recommended)**
   - Download from: http://www.bit-cluster.com/
   - Restore using: `mongorestore --db bitcoin <database-dump-directory>`
   
   **Option B: Build from scratch** (Advanced)
   - Install Bitcoin Core and sync the blockchain
   - Configure Bitcoin Core with RPC access
   - Run the clustering scripts (see Advanced Usage below)

6. **Configure database connection**
   Edit `settings/settings.py` if your MongoDB runs on different host/port:
   ```python
   db_server = "127.0.0.1"
   db_port = 27017
   ```

### Usage

**Start the Web Interface:**
```bash
python3 start_website.py
# or with custom options:
python3 start_website.py -p 5001 -d  # Port 5001, debug mode
```

**Start the REST API:**
```bash
python3 start_webapi.py
```

Visit `http://127.0.0.1:5000` (or your configured port) to explore Bitcoin address clusters and transactions.

## Advanced Usage

### Building Database from Scratch

**Note**: This process requires a fully synced Bitcoin Core node and can take significant time.

1. **Configure Bitcoin Core** (`bitcoin.conf`):
   ```
   server=1
   rpcallowip=127.0.0.1
   rpcport=8332
   txindex=1
   rpcuser=your_username
   rpcpassword=your_secure_password
   ```

2. **Build address clusters:**
   ```bash
   python3 build_cluster.py <starting_block_id>
   ```

3. **Map money flows:**
   ```bash
   python3 map_money.py <start_block_id> <end_block_id>
   ```

## Dependencies

Core dependencies (see `requirements.txt` for full list):
- **Flask** (3.1.1) - Web framework for UI and API
- **pymongo** (4.13.2) - MongoDB driver for database operations  
- **python-bitcoinlib** (0.12.2) - Bitcoin protocol implementation

## Configuration

Key settings in `settings/settings.py`:
- `db_server` - MongoDB server address (default: 127.0.0.1)
- `db_port` - MongoDB port (default: 27017)  
- `block_crawling_limit` - Blocks processed before DB sync (default: 2500)
- `max_batch_insert` - Maximum batch size for DB operations (default: 10000)
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

The MongoDB database contains two main collections:

**addresses**: Maps Bitcoin addresses to cluster node IDs
```json
{
  "_id": "1AbHNFdKJeVL8FRZyRZoiTzG9VCmzLrtvm",
  "n_id": 1
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
  "trx_date": "2010-08-17"
}
```

## Contributing

This project analyzes public Bitcoin blockchain data. Contributions for improvements, bug fixes, and new analysis features are welcome.

## License

Please refer to the project's license file for usage terms.

## Links

- **Project Repository**: https://github.com/mathieulavoie/Bitcluster
- **Installation Guide**: https://github.com/mathieulavoie/Bitcluster/wiki/Installation-procedure
- **Database Documentation**: https://github.com/mathieulavoie/Bitcluster/wiki/Database-structure
- **Official Website**: http://www.bit-cluster.com
