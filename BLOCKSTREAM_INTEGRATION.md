# Blockstream API Integration for Bitcluster

## Overview

This document outlines the plan to migrate Bitcluster from requiring a full Bitcoin Core node to using Blockstream's public API service. This will significantly reduce infrastructure requirements while providing real-time Bitcoin blockchain data.

## Research Findings

### Blockstream API Capabilities

**Base URL**: `https://blockstream.info/api/`

**Key Endpoints Tested**:
- **Blocks**: `/block/{hash}` - Full block information  
- **Addresses**: `/address/{address}` - Address balance, transaction count
- **Address Transactions**: `/address/{address}/txs` - Transaction list for address
- **Transaction Details**: `/tx/{txid}` - Complete transaction data including inputs/outputs
- **Address UTXO**: `/address/{address}/utxo` - Unspent transaction outputs

**Data Quality**: ✅ Excellent
- Real-time data with immediate confirmation
- Full transaction details including scriptpubkey, amounts, addresses
- Historical data back to genesis block
- JSON format perfectly suited for our MongoDB integration

### Rate Limiting Constraints

**Free Tier**: 500,000 requests/month (~16,667 requests/day)
**Pricing**: 
- 500,001-10M requests: $0.01 per 100 requests
- 10M-50M requests: $0.01 per 200 requests  
- 50M-100M requests: $0.01 per 500 requests
- Above 100M requests: $4,000/month flat rate

**Strategy**: Stay within free tier initially, implement aggressive caching

## Architecture Design

### Rate Limiting System

**Monthly Budget**: 500,000 requests
**Daily Budget**: ~16,667 requests  
**Hourly Budget**: ~694 requests
**Safety Buffer**: 20% (reserve 100,000 requests for month-end)

**Implementation**:
```python
class RateLimiter:
    def __init__(self):
        self.monthly_limit = 400000  # 80% of free tier
        self.daily_limit = 13333     # 80% of daily average
        self.hourly_limit = 555      # 80% of hourly average
        
    def check_limits(self):
        # Check MongoDB rate_limiting collection
        # Return (can_proceed, wait_time)
        
    def record_request(self, endpoint, response_size):
        # Log to MongoDB for tracking
```

### Caching Strategy

**Three-Tier Caching**:

1. **MongoDB Cache** (Persistent)
   - Cache all address lookups for 24 hours
   - Cache transaction details permanently 
   - Cache block data permanently

2. **Redis Cache** (Fast Access) 
   - Recently accessed addresses (1 hour TTL)
   - Active transaction monitoring
   - Rate limit counters

3. **Application Cache** (Memory)
   - Current session data
   - Frequently accessed addresses

### Data Pipeline Architecture

```
User Request → Cache Check → Rate Limit Check → Blockstream API → Cache Store → Response
```

**Cache Hit Optimization**:
- Target 90% cache hit rate for addresses
- Target 100% cache hit rate for old transactions
- Priority queue for new address discoveries

## Implementation Plan

### Phase 1: Core API Client ✨
**File**: `blockstream/api_client.py`

```python
class BlockstreamClient:
    def __init__(self):
        self.base_url = "https://blockstream.info/api"
        self.rate_limiter = RateLimiter()
        self.cache = CacheManager()
        
    async def get_address_info(self, address):
        # Check cache first
        # Apply rate limiting
        # Fetch from API if needed
        # Store in cache
        
    async def get_address_transactions(self, address):
        # Similar pattern for transactions
        
    async def get_transaction_details(self, txid):
        # Fetch full transaction data
```

### Phase 2: Data Processing Pipeline
**File**: `blockstream/data_processor.py`

```python
class DataProcessor:
    def __init__(self):
        self.client = BlockstreamClient()
        self.db = MongoDBConnection()
        
    async def process_address(self, address):
        # Fetch address data
        # Extract transactions
        # Update clustering algorithms
        # Store in format compatible with existing code
```

### Phase 3: Background Sync Service
**File**: `blockstream/sync_service.py`

```python
class BackgroundSyncService:
    def __init__(self):
        self.processor = DataProcessor()
        
    async def sync_new_transactions(self):
        # Monitor new blocks
        # Update tracked addresses
        # Maintain cache freshness
        
    async def discover_new_addresses(self):
        # Expand clustering based on new transactions
        # Batch process to respect rate limits
```

### Phase 4: Web Integration
**Updates**: Modify existing web interface to use new data source
- Update `web/dao.py` to use new data format
- Maintain API compatibility
- Add new endpoints for real-time data

## Database Schema Updates

### New Collections

**`blockstream_cache`**:
```javascript
{
  _id: "address:1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  data: { /* full address data */ },
  cached_at: ISODate(),
  expires_at: ISODate(),
  api_calls_made: 3
}
```

**`rate_limiting`**:
```javascript
{
  _id: "2025-01",
  monthly_count: 12450,
  daily_counts: {"2025-01-15": 450, "2025-01-16": 523},
  hourly_counts: {"2025-01-15:14": 23, "2025-01-15:15": 31},
  last_reset: ISODate()
}
```

**`transaction_cache`**:
```javascript
{
  _id: "txid:4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
  data: { /* full transaction data */ },
  cached_at: ISODate(),
  permanent: true  // transactions never change
}
```

## Migration Strategy

### Gradual Migration
1. **Week 1**: Implement API client and rate limiting
2. **Week 2**: Build caching layer and test with limited addresses  
3. **Week 3**: Integrate with existing clustering algorithms
4. **Week 4**: Full migration and monitoring

### Compatibility Layer
- Keep existing database schema
- Add new `data_source` field to track origin
- Gradual transition of queries to new API

### Monitoring & Alerts
- Daily rate limit usage reports
- Cache hit rate monitoring  
- API response time tracking
- Cost projection alerts

## Testing Strategy

### Load Testing
```bash
# Test with current sample data
python test_blockstream_integration.py --addresses sample_addresses.txt --max-requests 100

# Monitor rate limiting
python monitor_rate_limits.py --duration 1h

# Cache performance test  
python test_cache_performance.py --scenarios cache_hit,cache_miss,rate_limit
```

### Validation Testing
- Compare outputs with existing Bitcoin Core data
- Verify clustering algorithm compatibility
- Test web interface with new data source

## Expected Benefits

### Immediate
- ✅ No Bitcoin Core installation required
- ✅ No blockchain sync wait time (weeks → minutes)
- ✅ Real-time data access
- ✅ Reduced infrastructure costs

### Long-term  
- 📈 Faster address discovery
- 📈 Real-time transaction monitoring
- 📈 Easier deployment and scaling
- 📈 Always up-to-date blockchain data

## Risk Mitigation

### Rate Limit Exceeded
- **Prevention**: Aggressive caching, usage monitoring
- **Response**: Queue requests, prioritize by importance
- **Backup**: Temporary paid tier if critical

### API Downtime
- **Mitigation**: Cached data serves 90% of requests
- **Fallback**: Graceful degradation to cached-only mode
- **Monitoring**: Health checks and automatic retries

### Data Inconsistency
- **Validation**: Cross-check critical addresses
- **Rollback**: Keep old data during transition period
- **Testing**: Extensive validation before full migration

## Success Metrics

### Performance
- **Response Time**: < 200ms for cached requests, < 2s for API requests
- **Cache Hit Rate**: > 90% for addresses, > 95% for transactions  
- **Uptime**: > 99.5% availability

### Cost Efficiency
- **Monthly API Usage**: < 400,000 requests (stay in free tier)
- **Infrastructure Savings**: Eliminate Bitcoin Core server costs
- **Development Time**: 50% faster feature development

---

## Next Steps

1. **✅ Research Complete**: Blockstream API tested and documented
2. **🔄 In Progress**: Rate limiting architecture design
3. **⏳ Next**: Implement core API client with rate limiting
4. **⏳ Next**: Build caching layer
5. **⏳ Next**: Integration testing with current codebase

**Ready to proceed with implementation!** 🚀 