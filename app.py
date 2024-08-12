import json
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
from urllib.parse import quote
import logging
# import uuid

load_dotenv()

# logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://api.cashfree.com/pg/orders"

# In-memory storage for demo purposes; use a database in production
order_data_store = {}

@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.json
        logging.debug(f"Received data: {data}")

        order_id = data.get('order_id')
        if not order_id:
            logging.error("Order ID is missing in the request data")
            return jsonify({'error': 'Order ID is required'}), 400

        # Save the payment details
        # logging.info(f"Saving payment details for orderId: {order_id}")
        # logging.debug(f"Payment details: {data}")

        # order_amount = data.get('order_amount')
        # if not order_amount:
        #    logging.error("Order amount is missing in the request data")
        #    return jsonify({'error': 'Order amount is required'}), 400

        # Generate a unique reference ID for storing large data
        # data_reference_id = str(uuid.uuid4())
        # order_data_store[data_reference_id] = {
        #     'selected_numbers': data.get("selected_numbers", []),
        #     'selected_ranges': data.get("selected_ranges", []),
        #     'hou_heda_values': data.get("hou_heda_values", {}),
        #     'hou_jeda_values': data.get("hou_jeda_values", {}),
        #     'f_r_amounts': data.get("f_r_amounts", []),
        #     's_r_amounts': data.get("s_r_amounts", []),
        # }

        return_url = (
            f'https://teerkhelo.web.app/payment_response?order_id={quote(str(order_id))}'
            f'&status=success'
            # f'&user_name={quote(str(data.get("customer_name", "")))}'
            # f'&user_mobile_number={quote(str(data.get("customer_phone", "")))}'
            # f'&total_amount={quote(str(data.get("total_amount", "")))}'
            # f'&data_reference_id={quote(data_reference_id)}'
        )

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
    user_name = data.get('user_name')
    user_mobile_number = data.get('user_mobile_number')
    data_reference_id = data.get('data_reference_id')

    # Retrieve stored data using the reference ID
    stored_data = order_data_store.get(data_reference_id, {})

    # Debug logging
    logging.debug(f"Received data: {data}")
    logging.debug(f"Stored data: {stored_data}")

    # Verify the payment with Cashfree
    payment_verification_url = f'https://teerkhelo.web.app/pg/orders/{order_id}'
    headers = {
        'x-client-id': CASHFREE_APP_ID,
        'x-client-secret': CASHFREE_SECRET_KEY,
    }

    verification_response = requests.get(payment_verification_url, headers=headers)
    verification_data = verification_response.json()

    if verification_response.status_code == 200 and verification_data.get('order_status') == 'PAID':
        # Payment is verified
        return jsonify({
            'message': 'Payment verified',
            'order_id': order_id,
            'status': 'success',
            'redirect_url': 'image_screen',
            # 'user_name': user_name,
            # 'user_mobile_number': user_mobile_number,
            # 'selected_numbers': stored_data.get('selected_numbers', []),
            # 'selected_ranges': stored_data.get('selected_ranges', []),
            # 'hou_heda_values': stored_data.get('hou_heda_values', {}),
            # 'hou_jeda_values': stored_data.get('hou_jeda_values', {}),
            # 'f_r_amounts': stored_data.get('f_r_amounts', []),
            # 's_r_amounts': stored_data.get('s_r_amounts', [])
        })
    else:
        # Payment not verified
        return jsonify({
            'message': 'Payment verification failed',
            'order_id': order_id,
            'status': 'failed'
        })


@app.route('/payment_notification', methods=['POST'])
def payment_notification():
    data = request.form.to_dict()
    # Handle payment notification, usually updating the order status based on the notification.
    return jsonify({'message': 'Payment notification received', 'data': data})

if __name__ == '__main__':
    app.run(debug=False, ) # Turn off debug mode for production
# host='127.0.0.1', port=5000