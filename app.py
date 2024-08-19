import json
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import base64

# Read and decode the Firebase key
firebase_key_base64 = os.getenv('FIREBASE_KEY_BASE64')
if firebase_key_base64:
    firebase_key_json = base64.b64decode(firebase_key_base64).decode('utf-8')
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
else:
    raise ValueError("FIREBASE_KEY_BASE64 environment variable is not set")

db = firestore.client()

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://api.cashfree.com/pg/orders"

@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.json
        logging.debug(f"Received data: {data}")

        order_id = data.get('order_id')
        if not order_id:
            logging.error("Order ID is missing in the request data")
            return jsonify({'error': 'Order ID is required'}), 400
        
        return_url = f'https://teerkhelo.web.app/payment_response?order_id={order_id}'

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
                'customer_phone': data.get('customer_phone')
            },
            'order_meta': {
                'return_url': return_url
            }
        }

        logging.debug(f"Payload: {payload}")
        response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
        response_data = response.json()

        logging.debug(f"Response: {response_data}")

        if response.status_code == 200:
            payment_session_id = response_data.get('payment_session_id', '')
            if payment_session_id:
                # Create order data for Firestore
                orderData = {
                    "order_id": order_id,
                    "payment_status": "pending"  # Initialize payment_status field
                }

                # Save to Firestore
                try:
                    # Assuming the orders collection is directly under Firestore
                    orders_ref = db.collection('orders').document(order_id)
                    orders_ref.set(orderData, merge=True)
                    logging.info(f"Order {order_id} created with status: pending")

                    # Optionally, you can update the status here if needed
                    # update_order_status(order_id, 'pending')

                except Exception as e:
                    logging.error(f"Error updating Firestore: {e}")

                return jsonify({
                    'order_id': order_id,
                    'payment_session_id': payment_session_id
                })
            else:
                return jsonify({'error': 'Payment session ID not found'}), 500
        else:
            return jsonify({'error': response_data.get('message', 'Unknown error occurred')}), response.status_code

    except Exception as e:
        logging.error(f"Exception occurred: {e}")
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500


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
        # Payment is verified, update order status
        update_order_status(order_id, 'Order Completed')
        return jsonify({
            'message': 'Payment verified',
            'order_id': order_id,
            'redirect_url': 'image_screen',
        })
    else:
        # Payment not verified
        return jsonify({
            'message': 'Payment verification failed',
            'order_id': order_id,
        })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        order_id = data.get('order_id')
        payment_status = data.get('payment_status')
        
        if payment_status == 'SUCCESS':  # Adjust based on your payment gateway's success status
            # Update the order status in Firebase
            orders_ref = db.collection('orders')
            order_ref = orders_ref.document(order_id)
            order_ref.update({'payment_status': 'Order Completed'})
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'pending'}), 200

    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500


def update_order_status(order_id, status):
    try:
        # Reference to the orders collection
        orders_ref = db.collection('orders')
        # Update the specific order document
        orders_ref.document(order_id).update({'payment_status': status})
        logging.info(f"Order {order_id} updated with payment status: {status}")

    except Exception as e:
        logging.error(f"Error updating order status: {e}")


@app.route('/payment_notification', methods=['POST'])
def payment_notification():
    data = request.form.to_dict()
   
    return jsonify({'message': 'Payment notification received', 'data': data})

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
