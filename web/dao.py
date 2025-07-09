import operator
import logging
from pymongo import MongoClient
from settings import settings

logger = logging.getLogger(__name__)


client = MongoClient(settings.db_server, settings.db_port)
db = client.bitcoin

def getNodeFromAddress(address):
    cursor = db.addresses.find_one({"_id": address})
    return int(cursor['n_id']) if cursor is not None else None

def mapDirectionToField(direction):
    if direction not in ["in","out"]:
        return None
    return {"field":"destination_n_id" if direction == "in" else "source_n_id",
            "opposite_field" : "source_n_id" if direction == "in" else "destination_n_id"}

def getAddresses(node_id):
    if isinstance(node_id, str):
        node_id = int(node_id)

    addresses = []
    for addr in db.addresses.find({"n_id":node_id}):
        addresses.append(addr['_id'])
    return addresses

def getTransations(node_id,direction):
    if isinstance(node_id, str):
        node_id = int(node_id)

    direction = direction.lower()
    transactions = []
    columns = mapDirectionToField(direction)
    if columns is None:
        return

    object_fields = ['trx_date','block_id','source_n_id','destination_n_id','amount', 'amount_usd','source','destination']
    integers_fields = ['block_id','source_n_id','destination_n_id']
    for trx in db.transactions.find({"$and":[{columns['field']:node_id},{columns['opposite_field']:{"$ne":node_id}}]}):
        object = {}
        for f in object_fields:
            object[f] = int(trx[f]) if f in integers_fields else trx[f] #hack for mongoDB returning float

        transactions.append(object)
    return transactions

def groupByAllDistribution(transactions,direction):
    return {"by_node":groupbyNode(transactions,direction),
            "by_date": groupbyDate(transactions),
            "by_amount":groupbyAmount(transactions) }

def groupbyAmount(transactions):
    distribution_bitcoin = dict()
    distribution_usd = dict()
    for trx in transactions:
        key_bitcoin = trx['amount']
        key_usd = trx['amount_usd']
        if key_bitcoin in distribution_bitcoin:
           distribution_bitcoin[key_bitcoin] += 1
        else:
            distribution_bitcoin[key_bitcoin] = 1

        if key_usd in distribution_usd:
           distribution_usd[key_usd] += 1
        else:
            distribution_usd[key_usd] = 1

    return {"amount_btc":sorted(distribution_bitcoin.items(),key=operator.itemgetter(1),reverse=True),"amount_usd":sorted(distribution_usd.items(),key=operator.itemgetter(1),reverse=True)}

def groupbyNode(transactions,direction):
    nodes_group = dict()
    columns = mapDirectionToField(direction)
    if columns is None:
        return
    field = columns['opposite_field']
    for trx in transactions:
        key = trx[field]
        if key in nodes_group:
           nodes_group[key]['transactions'].append(trx)
           nodes_group[key]['amount_btc'] +=trx['amount']
           nodes_group[key]['amount_usd'] +=trx['amount_usd']
        else:
            nodes_group[key] = {"amount_btc": trx['amount'], "amount_usd": trx['amount_usd'], "transactions":[trx]}

    sorted_items = sorted(nodes_group.items(), key=lambda x : x[1]['amount_usd'], reverse=True)
    return sorted_items

def groupbyDate(transactions):
    group_by_date = dict()

    for trx in transactions:
        key = trx['trx_date']
        if key in group_by_date:
           group_by_date[key]['transactions'].append(trx)
           group_by_date[key]['amount_btc'] +=trx['amount']
           group_by_date[key]['amount_usd'] +=trx['amount_usd']
        else:
            group_by_date[key] = {"amount_btc": trx['amount'], "amount_usd": trx['amount_usd'], "transactions":[trx]}

    sorted_items = sorted(group_by_date.items(),key=operator.itemgetter(0))
    return sorted_items

def getAmountTotal(transactions):
    sum_btc = 0
    sum_usd = 0
    for trx in transactions:
        sum_btc += trx['amount']
        sum_usd += trx['amount_usd']
    return {"btc": sum_btc,"usd": sum_usd}



def getNodeInformation(node_id):
    transactions_in = getTransations(node_id,"in")
    transactions_out = getTransations(node_id,"out")
    incomes_grouped = groupByAllDistribution(transactions_in, "in")
    outcomes_grouped = groupByAllDistribution(transactions_out, "out")
    addresses = getAddresses(node_id)

    stats = {}
    stats['amounts_received'] = getAmountTotal(transactions_in)
    stats['amounts_sent'] = getAmountTotal(transactions_out)
    stats['distinct_sources_count'] = len(incomes_grouped['by_node'])
    stats['distinct_destination_count'] = len(outcomes_grouped['by_node'])
    stats['node_addresses_count']= len(addresses)

    activity_dates = list(map(lambda x : x[0],incomes_grouped['by_date'])) + list(map(lambda x : x[0],outcomes_grouped['by_date']))


    if len(activity_dates) > 0:
        stats['first_seen'] = min(activity_dates)
        stats['last_seen'] = max(activity_dates)


    information = {"node_id" : node_id}
    information['stats'] = stats
    information['incomes_grouped'] = incomes_grouped
    information['outcomes_grouped'] = outcomes_grouped
    information['node_addresses'] = addresses
    information['transactions'] = {'in': transactions_in, 'out':transactions_out}

    return information

def getCoinJoinTransactions(limit=100, offset=0, coinjoin_type=None):
    """
    Get CoinJoin transactions with optional filtering
    
    Args:
        limit: Maximum number of results
        offset: Skip this many results
        coinjoin_type: Filter by CoinJoin type ('joinmarket', 'wasabi', 'whirlpool') or None for all
        
    Returns:
        List of CoinJoin transaction records
    """
    query = {"is_coinjoin": True}
    if coinjoin_type:
        query["coinjoin_type"] = coinjoin_type
    
    transactions = list(db.transactions.find(query)
                       .sort("_id", -1)  # Most recent first
                       .skip(offset)
                       .limit(limit))
    
    return transactions

def getCoinJoinStats():
    """Get statistics about CoinJoin transactions with enhanced metrics"""
    try:
        collection = db.transactions
        
        # Enhanced aggregation pipeline for detailed statistics
        pipeline = [
            {"$match": {"is_coinjoin": True}},
            {"$group": {
                "_id": "$coinjoin_type",
                "count": {"$sum": 1},
                "avg_confidence": {"$avg": "$coinjoin_confidence"},
                "avg_participants": {"$avg": "$coinjoin_participants"},
                "total_participants": {"$sum": "$coinjoin_participants"},
                "min_confidence": {"$min": "$coinjoin_confidence"},
                "max_confidence": {"$max": "$coinjoin_confidence"},
                "denominations": {"$addToSet": "$coinjoin_denomination"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        service_stats = list(collection.aggregate(pipeline))
        
        # Overall statistics
        total_coinjoin = collection.count_documents({"is_coinjoin": True})
        total_transactions = collection.count_documents({})
        
        # High confidence transactions (>= 80%)
        high_confidence_count = collection.count_documents({
            "is_coinjoin": True, 
            "coinjoin_confidence": {"$gte": 0.8}
        })
        
        return {
            'total_coinjoin_transactions': total_coinjoin,
            'total_transactions': total_transactions,
            'coinjoin_percentage': (total_coinjoin / total_transactions * 100) if total_transactions > 0 else 0,
            'high_confidence_count': high_confidence_count,
            'high_confidence_percentage': (high_confidence_count / total_coinjoin * 100) if total_coinjoin > 0 else 0,
            'services': {
                stat['_id']: {
                    'count': stat['count'],
                    'percentage': (stat['count'] / total_coinjoin * 100) if total_coinjoin > 0 else 0,
                    'avg_confidence': round(stat['avg_confidence'], 3),
                    'avg_participants': round(stat['avg_participants'], 1) if stat['avg_participants'] else None,
                    'total_participants': stat['total_participants'],
                    'confidence_range': {
                        'min': round(stat['min_confidence'], 3),
                        'max': round(stat['max_confidence'], 3)
                    },
                    'unique_denominations': len([d for d in stat['denominations'] if d is not None])
                } for stat in service_stats if stat['_id']
            }
        }
    except Exception as e:
        logger.error(f"Error getting CoinJoin stats: {e}")
        return {
            'total_coinjoin_transactions': 0,
            'total_transactions': 0,
            'coinjoin_percentage': 0,
            'high_confidence_count': 0,
            'high_confidence_percentage': 0,
            'services': {}
        }