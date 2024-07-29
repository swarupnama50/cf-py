import uuid
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://api.cashfree.com/pg/orders"

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
        'order_meta': {
            'return_url': f'https://teerkhelo.web.app/payment_response?order_id={order_id}',
            'notify_url': 'https://teerkhelo.web.app/payment_notification'
        }
    }

    response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
    response_data = response.json()

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

    payment_url = "https://api.cashfree.com/checkout"

    payload = {
        'order_id': order_id,
        'order_amount': order_amount,
        'order_currency': 'INR',
        'return_url': f'https://teerkhelo.web.app/payment_response?order_id={order_id}'
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

@app.route('/payment_response', methods=['GET'])
def payment_response():
    data = request.args.to_dict()
    order_id = data.get('order_id')

    # Verify the payment with Cashfree
    payment_verification_url = f'https://api.cashfree.com/pg/orders/{order_id}'
    headers = {
        'x-client-id': CASHFREE_APP_ID,
        'x-client-secret': CASHFREE_SECRET_KEY,
    }

    verification_response = requests.get(payment_verification_url, headers=headers)
    verification_data = verification_response.json()

    if verification_response.status_code == 200 and verification_data.get('order_status') == 'PAID':
        # Payment is verified
        return jsonify({'message': 'Payment verified', 'order_id': order_id, 'status': 'success'})
    else:
        # Payment not verified
        return jsonify({'message': 'Payment verification failed', 'order_id': order_id, 'status': 'failed'})

@app.route('/payment_notification', methods=['POST'])
def payment_notification():
    data = request.form.to_dict()
    # Handle payment notification, usually updating the order status based on the notification.
    return jsonify({'message': 'Payment notification received', 'data': data})

if __name__ == '__main__':
    app.run(debug=False)  # Turn off debug mode for production
