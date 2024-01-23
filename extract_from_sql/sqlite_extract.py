import json
import sqlite3
from pathlib import Path

import requests
import logging

from paden.pad import database_eager


def fetch_full_order_column(db_path: Path) -> list:
    """
    Fetch the 'full_order' column from the 'jobs' table in the SQLite database.

    Args:
        db_path (Path): The path to the SQLite database file.

    Returns:
        list: A list of values from the 'full_order' column.
    """
    # Convert Path object to string for sqlite3 compatibility
    db_path_str = str(db_path)

    # Initialize an empty list to store the full_order values
    full_order_values = []

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path_str)

    try:
        # Create a cursor object
        cursor = conn.cursor()

        # Execute the SQL query to fetch the 'full_order' column
        cursor.execute("SELECT full_order FROM jobs")

        # Fetch all rows
        rows = cursor.fetchall()

        # Extract the 'full_order' values and append to the list
        for row in rows:
            full_order_values.append(row[0])

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

    return full_order_values


def save_to_json(data: dict, output_folder: Path):
    """
    Save the dictionary to a JSON file.

    Args:
        data (dict): The data to be saved.
        output_folder (Path): The folder where the JSON file will be saved.
    """
    order_item_number = data.get("orderItemNumber", "unknown")
    file_path = output_folder / f"{order_item_number}.json"

    with file_path.open("w") as f:
        json.dump(data, f, indent=4)


def send_to_api(parsed_data: dict, api_url: str):
    """
    Sends parsed data to a specified API endpoint using an HTTP POST request.

    Args:
        parsed_data (dict): The data to be sent to the API.
        api_url (str): The endpoint URL of the API.

    Returns:
        Response: The response from the API.
    """
    response = requests.post(api_url, json=parsed_data)
    return response


##############
def fetch_unsent_orders(database_path: Path):
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE status = 'SENTTOSUPPLIER'")
        unsent_orders = cursor.fetchall()
    return unsent_orders


def mark_as_received_by_vila(database_path: Path, order_id: int):
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status = 'ORDER_RECEIVEDBYVILA' WHERE id = ?", (order_id,))
        conn.commit()


def update_order_status(database_path: Path, order_id: int, new_status: str):
    """
    Update the status of an order in the database.

    Args:
        database_path (Path): Path to the SQLite database file.
        order_id (int): ID of the order to update.
        new_status (str): New status to set for the order.
    """
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()

def collect_orders_from_database_():
    database_path = database_eager
    api_url = "http://localhost:8000/collect_printcom_order_item"

    unsent_orders = fetch_unsent_orders(database_path)

    for order_id, status, order_item, full_order, timestamp in unsent_orders:
        try:
            parsed_data = json.loads(full_order)
            response = send_to_api(parsed_data, api_url)

            if response.status_code == 200:  # Assuming 200 is a successful response
                mark_as_received_by_vila(database_path, order_id)
                logging.info(f"Order {order_id}: {order_item} sent successfully. Updating status.")
                print(f"Order {order_id}: {order_item} sent successfully and status updated.")

        except json.JSONDecodeError:
            print(f"Unable to parse order: {order_id}")
            logging.error(f"Unable to parse order: {order_id}")




def collect_orders_from_database(api_instance):
    database_path = "jobs_eager.db"
    api_url = "http://localhost:8000/collect_printcom_order_item"
    new_status = "ACCEPTEDBYSUPPLIER"  # Replace with the desired new status
    message = ""  # Replace with your custom message

    logging.info("Collecting unsent orders from the database.")
    unsent_orders = fetch_unsent_orders(database_path)

    for order_id, status, order_item, full_order, timestamp in unsent_orders:
        try:
            parsed_data = json.loads(full_order)
            logging.info(f"Sending order {order_id} to the API.")
            response = send_to_api(parsed_data, api_url)

            if response.status_code == 200:  # Assuming 200 is a successful response
                logging.info(f"Order {order_id} {order_item} sent successfully. Updating status.")
                if api_instance.update_job_status_with_message(order_item, new_status, message):
                    logging.info(f"Order {order_id}: {order_item} status updated to {new_status}.")

                    mark_as_received_by_vila(database_path, order_id)
                    print(f"Order {order_id}: {order_item} sent successfully and status updated.")
                else:
                    logging.error(f"Failed to update status for Order {order_id}: {order_item}")
            else:
                logging.error(f"API response for order {order_id} was not successful: Status Code {response.status_code}")

        except json.JSONDecodeError as e:
            logging.error(f"Unable to parse order {order_id}: {e}")





def fetch_order_items_for_update(db_path, status_to_update):
    """
    Fetch order item numbers from the database for a specific status.

    Args:
        db_path (str): Path to the SQLite database file.
        status_to_update (str): Status of the order items to fetch.

    Returns:
        list: A list of order item numbers.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query to select order items based on a specific status
    cursor.execute("SELECT order_item FROM jobs WHERE status = ?", (status_to_update,))
    order_items = cursor.fetchall()

    conn.close()
    return [item[0] for item in order_items]  # Extracting order_item numbers from the query results


def update_order_items_status(api_instance, order_items, new_status, message):
    """
    Update the status of each order item using the PrintDotComAPI.

    Args:
        api_instance (PrintDotComAPI): Instance of the PrintDotComAPI class.
        order_items (list): List of order item numbers to update.
        new_status (str): The new status to set for each order item.
        message (str): Message to include with the status update.

    Returns:
        None
    """
    for item_id in order_items:
        api_instance.update_job_status_with_message(item_id, new_status, message)

# Usage example
# db_path = "path/to/your/database.db"  # Replace with the actual path to your database
# status_to_fetch = "SomeStatus"  # Replace with the actual status you want to fetch
# new_status = "ACCEPTEDBYSUPPLIER"  # The new status you want to set
# message = "Order accepted by supplier"  # Your custom message
#
# # Fetch order items
# order_items_to_update = fetch_order_items_for_update(db_path, status_to_fetch)
#
# # Update the status of each order item
# update_order_items_status(api_real, order_items_to_update, new_status, message)



if __name__ == "__main__":
    # Replace this with the path to your SQLite database
    # database_path = Path(r"/Users/mike10h/PycharmProjects/pythonProject_Resellers_API/jobs_eager.db")
    # api_url = "http://lloopt vandaag allemaal weer goedocalhost:8000/collect_printcom_order_item"
    # # Fetch and print the 'full_order' column values
    # full_order_data = fetch_full_order_column(database_path)
    # print("Values in 'full_order' column:", full_order_data[0])
    #
    # # output_folder = Path("downloads_eager")
    #
    #
    # # Create the output folder if it doesn't exist
    # # output_folder.mkdir(parents=True, exist_ok=True)
    #
    # for item in full_order_data:
    #     try:
    #         parsed_data = json.loads(item)
    #
    #         # save_to_json(parsed_data, output_folder)
    #         response = send_to_api(parsed_data, api_url)
    #         print(f"Response from API: {response.status_code}, {response.text}")
    #     except json.JSONDecodeError:
    #         print(f"Unable to parse item: {item}")
    #
    # print("JSON files have been saved.")
    collect_orders_from_database_()
    print('collect_orders_from_database: done')
    ...



