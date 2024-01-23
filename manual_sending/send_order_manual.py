import json
import logging
import sqlite3

from paden.pad import database_eager


def fetch_order_by_item(database_path: str, order_item: str):
    """
    Fetch a specific order from the database using the order_item.

    Args:
        database_path (str): Path to the SQLite database.
        order_item (str): The order_item identifier of the order to fetch.

    Returns:
        tuple: The fetched order data or None if not found.
    """
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE order_item = ?", (order_item,))
        order = cursor.fetchone()
    return order

import requests
import logging

def send_order_to_fastapi(api_url, order_data):
    """
    Send order data to a FastAPI endpoint via POST request.

    Args:
        api_url (str): URL of the FastAPI endpoint.
        order_data (dict): The order data to be sent.

    Returns:
        Response object: The response from the FastAPI server.
    """
    try:
        response = requests.post(api_url, json=order_data)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        return response
    except requests.RequestException as e:
        logging.error(f"Error sending data to FastAPI: {e}")
        return None


def collect_and_send_order(database_path, order_item):
    """
    Collect a specific order from the database based on order_item and send it to the FastAPI endpoint.

    Args:
        database_path (str): Path to the SQLite database.
        order_item (str): The order_item identifier of the order to send.

    Returns:
        None
    """
    api_url = "http://localhost:8000/collect_printcom_order_item"
    order = fetch_order_by_item(database_path, order_item)

    if order:
        order_id, status, order_item, full_order, timestamp = order
        parsed_order = json.loads(full_order)

        response = send_order_to_fastapi(api_url, parsed_order)

        if response and response.status_code == 200:
            logging.info(f"Order {order_id} (Item {order_item}) sent successfully to FastAPI.")
        else:
            logging.error(f"Failed to send order {order_id} (Item {order_item}) to FastAPI.")
    else:
        logging.info(f"No order found for item {order_item}.")


# Usage
database_path = database_eager

# order_item_to_send = "6001202718-1"
# ERROR:root:Error sending data to FastAPI: 422 Client Error: Unprocessable Entity for url: http://localhost:8000/collect_printcom_order_item
# ERROR:root:Failed to send order 1951 (Item 6001202718-1) to FastAPI.
# order_item_to_send = "6001204647-1"  # Replace with the specific order_item identifier
# order_item_to_send = "6001206351-1"  # Replace with the specific order_item identifier
#ERROR:root:Error sending data to FastAPI: 422 Client Error: Unprocessable Entity for url: http://localhost:8000/collect_printcom_order_item
#ERROR:root:Failed to send order 2020 (Item 6001204647-1) to FastAPI.
order_item_to_send = "6001207895-1"
collect_and_send_order(database_path, order_item_to_send)
