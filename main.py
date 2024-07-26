import uuid
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
import urllib.parse


load_dotenv()

app = Flask(__name__)
CORS(app)

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://sandbox.cashfree.com/pg/orders"


@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.json
    order_id = data.get('order_id', str(uuid.uuid4()))
    order_amount = data.get('order_amount')
    order_currency = 'INR'
    customer_id = data.get('customer_id', 'default_customer_id')
    customer_name = data.get('customer_name', 'teerkhelo')
    customer_email = data.get('customer_email', 'teerkhelo@gmail.com')
    customer_phone = data.get('customer_phone', '9612388891')

    headers = {
        'Content-Type': 'application/json',
        'x-client-id': CASHFREE_APP_ID,
        'x-client-secret': CASHFREE_SECRET_KEY,
        'x-api-version': '2023-08-01'
    }

    payload = {
        'order_id': order_id,
        'order_amount': order_amount,
        'order_currency': order_currency,
        'customer_details': {
            'customer_id': customer_id,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone
        },
        'return_url': 'http://localhost:5000/payment_response',
        'notify_url': 'http://localhost:5000/payment_notification'
    }

    response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
    response_data = response.json()

    print(f"API Response: {response_data}")

    if response.status_code == 200:
        payment_session_id = response_data.get('payment_session_id', '')
        if payment_session_id:
            return jsonify({
                'order_id': order_id,
                'payment_session_id': payment_session_id
            })
        else:
            return jsonify({'error': 'Payment session ID not found'}), 500
    else:
        return jsonify({'error': response_data.get('message', 'Unknown error occurred')}), response.status_code




@app.route('/initiate_payment', methods=['POST'])
def initiate_payment():
    data = request.json
    order_id = data.get('order_id')
    order_amount = data.get('order_amount')

    payment_url = "https://sandbox.cashfree.com/checkout"

    payload = {
        'order_id': order_id,
        'order_amount': order_amount,
        'order_currency': 'INR',
        'return_url': 'http://localhost:5000/payment_response',
    }

    response = requests.post(payment_url, json=payload, headers={
        'Content-Type': 'application/json',
        'x-client-id': CASHFREE_APP_ID,
        'x-client-secret': CASHFREE_SECRET_KEY,
    })

    if response.status_code == 200:
        data = response.json()
        return jsonify({'payment_url': data.get('payment_url')})
    else:
        return jsonify({'error': 'Failed to initiate payment'}), response.status_code

@app.route('/payment_response', methods=['POST'])
def payment_response():
    data = request.form.to_dict()
    return jsonify(data)

@app.route('/payment_notification', methods=['POST'])
def payment_notification():
    data = request.form.to_dict()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)


