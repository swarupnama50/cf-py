import json
import time
from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
import logging
from flask import Flask
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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

app = Flask(__name__)
CORS(app)
CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY')
CASHFREE_API_URL = "https://api.cashfree.com/pg/orders"
# CASHFREE_API_URL = "https://sandbox.cashfree.com/pg/orders"

# CREATE ORDER
@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        data = request.json
        order_id = data.get('order_id')
        customer_email = data.get('customer_phone')
        customer_phone = '0000000000'

        return_url = f'https://teerkhelo.web.app/payment_response?order_id={order_id}'
        # return_url = f'http://localhost:9538/payment_response?order_id={order_id}'
        notify_url = 'https://cf-py-bvfc.onrender.com/webhook'

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
                'customer_email': customer_email,
                'customer_phone': customer_phone
            },
            'order_meta': {
                'return_url': return_url,
                'notify_url': notify_url
            }
        }

        response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
        response_data = response.json()
        app.logger.debug(f"Cashfree response data: {response_data}")

        if response.status_code == 200:
            payment_session_id = response_data.get('payment_session_id', '')

            # Save order and payment session id to Firestore
            order_ref = db.collection('orders').document(order_id)
            order_ref.set({
                'order_amount': data.get('order_amount'),
                'payment_session_id': payment_session_id
            })

            return jsonify({
                'order_id': order_id,
                'payment_session_id': payment_session_id
            })
        else:
            return jsonify({'error': response_data.get('message', 'Unknown error occurred')}), response.status_code

    except Exception as e:
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500


# RESUME PAYMENT
@app.route('/resume_payment', methods=['POST'])
def resume_payment():
    try:
        app.logger.debug("Resume payment started")
        data = request.json
        order_id = data.get('order_id')
        customer_email = data.get('customer_email')
        

        app.logger.debug(f"Data received: order_id={order_id}, customer_email={customer_email}")

        return_url = f'https://teerkhelo.web.app/payment_response?order_id={order_id}'
        # return_url = f'http://localhost:9538/payment_response?order_id={order_id}'
        notify_url = 'https://cf-py-bvfc.onrender.com/webhook'

        headers = {
            'Content-Type': 'application/json',
            'x-client-id': CASHFREE_APP_ID,
            'x-client-secret': CASHFREE_SECRET_KEY,
            'x-api-version': '2023-08-01'
        }

        # Check if order exists in Firestore
        app.logger.debug("Checking if order exists in Firestore")
        user_ref = db.collection('users').document(customer_email)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            orders = user_data.get('orders', {})
            if order_id in orders:
                app.logger.info(f"Order {order_id} found in Firestore.")
                order_details = orders[order_id]
                stored_payment_session_id = order_details.get('payment_session_id')

                if stored_payment_session_id:
                    app.logger.info(f"Using stored payment session ID for order {order_id}")
                    return jsonify({
                        'order_id': order_id,
                        'payment_session_id': stored_payment_session_id
                    })

                # If no stored payment session ID, check with Cashfree
                check_order_url = f'{CASHFREE_API_URL}/{order_id}'
                check_response = requests.get(check_order_url, headers=headers)

                if check_response.status_code == 200:
                    check_data = check_response.json()
                    if check_data.get('order_status') in ['PAID', 'EXPIRED']:
                        # Create a new order with a new ID
                        new_order_id = f"{order_id}_retry_{int(time.time())}"
                    else:
                        # Use existing order ID and payment session
                        return jsonify({
                            'order_id': order_id,
                            'payment_session_id': check_data.get('payment_session_id')
                        })
                else:
                    app.logger.info(f"Order {order_id} not found in Cashfree. Creating new payment session.")
                    new_order_id = order_id  # Use the existing order ID

                # Create a new payment session
                payload = {
                    'order_id': new_order_id,
                    'order_amount': order_details.get('order_amount'),
                    'order_currency': 'INR',
                    'customer_details': {
                        'customer_id': f'customer_{new_order_id}',
                        'customer_name': user_data.get('name', 'Customer'),
                        'customer_email': user_data.get('customer_email'),
                        'customer_email': customer_email
                    },
                    'order_meta': {
                        'return_url': return_url,
                        'notify_url': notify_url
                    }
                }

                response = requests.post(CASHFREE_API_URL, json=payload, headers=headers)
                response_data = response.json()

                app.logger.debug(f"Cashfree response: Status code: {response.status_code}, Data: {response_data}")

                if response.status_code == 200:
                    payment_session_id = response_data.get('payment_session_id', '')
                    
                    # Update Firestore with new order details
                    user_ref.update({
                        f'orders.{new_order_id}': {
                            'order_amount': order_details.get('order_amount'),
                            'payment_session_id': payment_session_id,
                            'payment_status': 'pending',
                            'original_order_id': order_id if new_order_id != order_id else None
                        }
                    })

                    # Update separate 'orders' collection
                    db.collection('orders').document(new_order_id).set({
                        'order_amount': order_details.get('order_amount'),
                        'payment_session_id': payment_session_id
                    }, merge=True)

                    return jsonify({
                        'order_id': new_order_id,
                        'payment_session_id': payment_session_id
                    })
                else:
                    return jsonify({'error': response_data.get('message', 'Unknown error occurred')}), response.status_code

            else:
                return jsonify({'error': 'Order ID not found in user orders'}), 404
        else:
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        app.logger.error(f"An error occurred: {str(e)}")
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500
    

def update_databases_with_new_order(old_order_id, new_order_id, payment_session_id, customer_email, old_order_data):
    try:
        # Update Realtime Database
        ref = db.reference('orders')
        ref.child(new_order_id).set(old_order_data)
        ref.child(new_order_id).update({
            'order_id': new_order_id,
            'payment_session_id': payment_session_id,
            'original_order_id': old_order_id
        })

        # Update Firestore
        user_ref = firestore.client().collection('users').document(customer_email)
        user_ref.update({
            f'orders.{new_order_id}': {
                'order_id': new_order_id,
                'order_ref': f'orders/{new_order_id}',
                'order_time': old_order_data.get('order_time'),
                'payment_status': 'pending',
                'original_order_id': old_order_id
            }
        })

        app.logger.info(f"Updated databases with new order {new_order_id} based on {old_order_id}")
    except Exception as e:
        app.logger.error(f"Error updating databases with new order: {str(e)}")




@app.route('/payment_response', methods=['GET'])
def payment_response():
    data = request.args.to_dict()
    order_id = data.get('order_id')

    # Verify the payment with Cashfree
    payment_verification_url = f'https://api.cashfree.com/pg/orders/{order_id}'
    # payment_verification_url = f'https://sandbox.cashfree.com/pg/orders/{order_id}'
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
        logging.debug(f"Received webhook data: {data}")

        order_id = data.get('data', {}).get('order', {}).get('order_id')
        payment_status = data.get('data', {}).get('payment', {}).get('payment_status')
        customer_email = data.get('data', {}).get('customer_details', {}).get('customer_email')

        if not order_id or not payment_status or not customer_email:
            logging.error("Required data is missing in the webhook.")
            return jsonify({'status': 'error', 'message': 'Invalid data received'}), 400

        # Update the payment status
        if payment_status == 'SUCCESS':
            update_order_status(order_id, 'Order Completed', customer_email)
        else:
            update_order_status(order_id, payment_status.capitalize(), customer_email)

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    


def update_order_status(order_id, status, customer_email):
    try:
        # Update the specific order document under the user's document
        user_ref = db.collection('users').document(customer_email)
        user_ref.update({
            f'orders.{order_id}.payment_status': status
        })

         # Update Realtime Database
        db.reference(f'orders/{order_id}/payment_status').set(status)


        logging.info(f"Order {order_id} updated with payment status: {status}")
    except Exception as e:
        logging.error(f"Error updating order status: {e}")




@app.route('/payment_notification', methods=['POST'])
def payment_notification():
    try:
        data = request.json
        order_id = data.get('order_id')
        payment_status = data.get('payment_status')

        if order_id and payment_status:
            if payment_status == 'SUCCESS':
                # Update the order status in Firestore
                orders_ref = db.collection('orders')
                order_ref = orders_ref.document(order_id)
                order_ref.update({'payment_status': 'Order Completed'})
                return jsonify({'status': 'success', 'message': 'Payment status updated'}), 200
            else:
                # Handle other statuses or errors as needed
                return jsonify({'status': 'failure', 'message': 'Payment not successful'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid data received'}), 400
    except Exception as e:
        logging.error(f"Error processing payment notification: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=False)
    # app.run(debug=True, host='127.0.0.1', port=5000)