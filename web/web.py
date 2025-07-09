#from web import app
from web.dao import getNodeFromAddress, getNodeInformation, getTransations, groupByAllDistribution, groupbyNode, \
    groupbyAmount, groupbyDate
from flask import *
import re
import csv
import io
from datetime import datetime, timedelta


app = Flask(__name__)

def format_btc(value):
    """Format Bitcoin amount with exactly 8 decimal places, no scientific notation"""
    if value is None:
        return "0.00000000"
    return f"{float(value):.8f}"

app.jinja_env.filters['format_btc'] = format_btc


@app.route('/',methods=['POST', 'GET'])
def web_root():
    if request.method == 'POST':
        address = request.form['q'].strip()  # Remove leading/trailing whitespace
        if address.isnumeric():
            return redirect(url_for('get_node_request',node_id=address))
        else:
            # Support all Bitcoin address formats: Legacy (1..., 3...), Bech32 (bc1q...), Bech32m (bc1p...)
            pattern = re.compile("^(bc1[a-z0-9]{39,59}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
            if pattern.match(address):
                node_id = getNodeFromAddress(address)
                if node_id is not None:
                    return redirect(url_for('get_node_request',node_id=node_id))
                
            return render_template('index.html',message="Invalid or inexistant address")

            
        


    return render_template('index.html')




@app.route('/nodes/<int:node_id>')
def get_node_request(node_id):
    infos = getNodeInformation(node_id)
    limit =100
    truncated_trx_in,trx_in = trim_collection(infos['transactions']['in'],limit)
    truncated_trx_out,trx_out = trim_collection(infos['transactions']['out'],limit)
    truncated_by_node_in,infos['incomes_grouped']['by_node'] = trim_collection(infos['incomes_grouped']['by_node'],limit)
    truncated_by_node_out,infos['outcomes_grouped']['by_node'] = trim_collection(infos['outcomes_grouped']['by_node'],limit)
    truncated_by_amount_in,infos['incomes_grouped']['by_amount']['amount_usd'] = trim_collection(infos['incomes_grouped']['by_amount']['amount_usd'],limit)
    truncated_by_amount_out,infos['outcomes_grouped']['by_amount']['amount_usd'] = trim_collection(infos['outcomes_grouped']['by_amount']['amount_usd'],limit)


 
    infos['transactions'] = {'in': trx_in, 'out':trx_out}

    return render_template('node_details.html',informations=infos, truncated=(truncated_trx_in or truncated_trx_out or truncated_by_node_in or truncated_by_node_out or truncated_by_amount_in or truncated_by_amount_out))


def trim_collection(collection, limit):
    if len(collection) > limit:
        return True, collection[0:limit]
    return False, collection



@app.route('/nodes/<int:node_id>/download/json/<direction>')
def download_transations_json(node_id,direction):
    if direction not in ["in","out"]:
        return Response(response="Invalid direction",status=500)

    transactions = getTransations(node_id,direction)
    grouped = groupByAllDistribution(transactions,direction)
    response = jsonify({"transactions":transactions, "groups":grouped})
    response.headers['Content-disposition'] = "attachment;filename=transactions_%d_%s.json"% (node_id, direction)
    return response


@app.route('/nodes/<int:node_id>/download/csv/<direction>')
def download_transations_csv(node_id,direction):
    if direction not in ["in","out"]:
        return Response(response="Invalid direction",status=500)
    
    output = io.StringIO()
    fieldnames = ['trx_date','block_id','source_n_id','destination_n_id','amount', 'amount_usd','source','destination']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for trx in getTransations(node_id,direction):
        writer.writerow(trx)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition":"attachment; filename=transactions_%d_%s.csv"% (node_id, direction)})


@app.route('/nodes/<int:node_id>/download/csv/<direction>/<grouping>')
def download_grouped_transactions(node_id,direction,grouping):
    if direction not in ["in","out"]:
        return Response(response="Invalid direction",status=500)
    
    output = io.StringIO()
    transactions = getTransations(node_id,direction)

    writer = csv.writer(output)
    if grouping == "by_node":
        writer.writerow(['node_id','amount_usd','amount_btc','transaction_count'])
        for k,v in groupbyNode(transactions,direction):
            writer.writerow([k,v['amount_usd'],v['amount_btc'],len(v['transactions'])])

    elif grouping == "by_amount":
        writer.writerow(['amount_usd','frequency'])
        for k,v in groupbyAmount(transactions)['amount_usd']:
            writer.writerow([k,v])

    elif grouping == "by_date":
        date_format = '%Y-%m-%d'
        sorted_by_date = groupbyDate(transactions)

        min_date = datetime.strptime(sorted_by_date[0][0],date_format)
        max_date = datetime.strptime(sorted_by_date[-1][0],date_format)
        delta = max_date - min_date

        index = 0
        writer.writerow(['date','amount_usd','amount_btc','transaction_count'])
        for date in [min_date + timedelta(days=x) for x in range(0,delta.days+1)]:
            strdate = date.strftime(date_format)
            k,v = sorted_by_date[index]
            if k == strdate:    
                writer.writerow([k,v['amount_usd'],v['amount_btc'],len(v['transactions'])])
                index +=1
            else:
                writer.writerow([strdate,0,0,0])
    else:
        return Response(response="Invalid grouping. Possible options : by_node , by_amount , by_date",status=500)


    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition":"attachment; filename=transactions_%d_%s_%s.csv"% (node_id, direction,grouping)})


