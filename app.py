from flask import Flask, request, jsonify
import pika
import traceback
import logging
import socket  # Import the socket module
import db.connectToDb
from service.getTempService import get_all_temperatures, get_temperature_by_room_id
from service.insertTempService import insert_temperature, insert_multiple_temperatures
from service.updateTempService import update_temperature_by_room_id
from service.deleteTempService import delete_by_room_id, delete_all_temperatures
 
app = Flask(__name__)
 
# Configure logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
 
 
@app.route('/publish/', methods=['POST'])
def publish_message():
    logger.debug("Received request at /publish/")
    try:
        # Connect to RabbitMQ.  Use a try-except block for connection errors.
        try:
            # Resolve the hostname to an IP address *before* connecting.
            try:
                rabbitmq_ip = socket.gethostbyname('rabbitmq')
                logger.debug(f"Resolved 'rabbitmq' to IP address: {rabbitmq_ip}")
                connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_ip))
            except socket.gaierror as e:
                logger.error(f"DNS resolution failed for 'rabbitmq': {e}")
                return jsonify({"status": "error", "message": f"Could not resolve hostname 'rabbitmq'.  Check your network configuration or ensure RabbitMQ is accessible at this hostname: {e}"}), 500
 
            channel = connection.channel()
            logger.debug("Connected to RabbitMQ")
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Could not connect to RabbitMQ: {e}")
            return jsonify({"status": "error", "message": f"Could not connect to RabbitMQ: {e}"}), 500
 
        # Declare queue
        channel.queue_declare(queue='hello')
        logger.debug("Queue 'hello' declared")
 
        # Get message from request.  Handle the case where the request is not JSON or 'message' is missing.
        try:
            data = request.get_json()
            logger.debug(f"Received JSON data: {data}")
            if not isinstance(data, dict):
                logger.error("Request must be JSON")
                return jsonify({"status": "error", "message": "Request must be JSON"}), 400
            message = data.get('message', 'Hello World!')
            if message is None:
                logger.error("'message' key is missing or null in the JSON payload")
                return jsonify({"status": "error", "message": "'message' key is missing or null in the JSON payload"}), 400
        except Exception as e:
            logger.error(f"Error parsing JSON: {e}")
            return jsonify({"status": "error", "message": f"Error parsing JSON: {e}"}), 400
 
        # Publish message
        try:
            channel.basic_publish(exchange='', routing_key='hello', body=message.encode('utf-8'))
            connection.close()
            logger.debug(f"Published message: {message}")
        except Exception as e:
            # Handle errors during publishing
            connection.close()
            logger.error(f"Error publishing message: {e}")
            return jsonify({"status": "error", "message": f"Error publishing message: {e}"}), 500
 
        return jsonify({"status": "Message published", "message": message}), 200
 
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {e}", "traceback": traceback.format_exc()}), 500
 
@app.route('/temps/createAndGetData', methods=['GET'])
def create_data():
    try:
        rows = db.connectToDb.connect_to_db()
        return jsonify({
            "status": "success",
            "message": "Data created and retrieved successfully",
            "data": rows  # This should be a list, not a set
        }), 200
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/updateTemperature', methods=['PUT'])
def update_temperature():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON body is required"}), 400

        room_id = data.get("room_id")
        new_temp = data.get("temperature")

        if room_id is None or new_temp is None:
            return jsonify({"status": "error", "message": "Both 'room_id' and 'temperature' are required"}), 400

        updated_row = db.connectToDb.update_temperature(room_id, new_temp)
        if not updated_row:
            return jsonify({"status": "error", "message": f"No room found with ID {room_id}"}), 404

        return jsonify({
            "status": "success",
            "message": f"Temperature updated for room {room_id}",
            "updated_data": updated_row
        }), 200

    except Exception as e:
        logger.error(f"Error updating temperature: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
  # GET APIs
@app.route('/temps', methods=['GET'])
def get_all():
    return jsonify(get_all_temperatures())

@app.route('/temps/<int:room_id>', methods=['GET'])
def get_by_id(room_id):
    return jsonify(get_temperature_by_room_id(room_id))

# INSERT APIs
@app.route('/temps', methods=['POST'])
def insert_one():
    data = request.json
    temp = data.get('temperature')
    new_id = insert_temperature(temp)
    return jsonify({'inserted_id': new_id})

@app.route('/temps/batch', methods=['POST'])
def insert_many():
    data = request.json
    temps = data.get('temperature_list', [])
    count = insert_multiple_temperatures(temps)
    return jsonify({'rows_inserted': count})

# UPDATE APIs
@app.route('/temps/<int:room_id>', methods=['PUT'])
def update_temp(room_id):
    data = request.json
    new_temp = data.get('temperature')
    rows = update_temperature_by_room_id(room_id, new_temp)
    return jsonify({'rows_updated': rows})

# DELETE APIs
@app.route('/temps/<int:room_id>', methods=['DELETE'])
def delete_id(room_id):
    rows = delete_by_room_id(room_id)
    return jsonify({'rows_deleted': rows})

@app.route('/temps', methods=['DELETE'])
def delete_all():
    rows = delete_all_temperatures()
    return jsonify({'rows_deleted': rows})
 
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
 
 
