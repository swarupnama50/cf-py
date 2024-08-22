# netlify/functions/create_order.py
import json
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__)

load_dotenv()

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://api.cashfree.com/pg/orders"

@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.json
        order_id = data.get('order_id')
        user_phone_number = data.get('customer_phone')

        return_url = f'https://teerkhelo.web.app/payment_response?order_id={order_id}'
        notify_url = 'https://cf-py.onrender.com/webhook'

        headers = {
            'Content-Type': 'application/json',
            'x-client-id': CASHFREE_APP_ID,
            'x-client-secret': CASHFREE_SECRET_KEY,
            'x-api-version': '2023-08-01'
        }

        payload = {
            'order_id': order_id,
            'order_amount': data.get('order_amount'),
            'order_currency': 'INR',
            'customer_details': {
                'customer_id': data.get('customer_id', 'default_customer_id'),
                'customer_name': data.get('customer_name'),
                'customer_email': data.get('customer_email'),
                'customer_phone': user_phone_number
            },
            'order_meta': {
                'return_url': return_url,
                'notify_url': notify_url
            }
        }

        response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            payment_session_id = response_data.get('payment_session_id', '')

            return jsonify({
                'order_id': order_id,
                'payment_session_id': payment_session_id
            })
        else:
            return jsonify({'error': response_data.get('message', 'Unknown error occurred')}), response.status_code

    except Exception as e:
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500

# Export handler for Netlify
def handler(event, context):
    return app(event, context)
