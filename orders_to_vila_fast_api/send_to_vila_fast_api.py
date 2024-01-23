import logging
from typing import List, Dict, Tuple
import requests
from loguru import logger


def send_token_to_server(token: str) -> None:
    """
    Sends a token string to the FastAPI server.

    Args:
        token (str): The token string to be sent.
    """
    # Define the URL of the FastAPI endpoint
    url = "http://127.0.0.1:8000/send-token/"

    # Create the payload containing the token
    payload = {"token": token}

    # Send a POST request to the FastAPI server
    response = requests.post(url, json=payload)

    # Check if the request was successful
    if response.status_code == 200:
        print("Successfully sent token. Server response:", response.json())
        logger.info(f"Successfully sent token. Server response: {response.json()}")
    else:
        print("Failed to send token. Status code:", response.status_code)
        logger.error(f"Failed to send token. Status code: {response.status_code}")


# Example usage



def send_to_fastapi(data: Dict, endpoint_url: str) -> int:
    """
    Send JSON data to a FastAPI endpoint.

    Args:
        data (Dict): The data to send.
        endpoint_url (str): The URL of the FastAPI endpoint.

    Returns:
        int: The HTTP status code from the FastAPI server.
    """
    response = requests.post(endpoint_url, json=data)
    return response.status_code


def send_list_to_vila_fast_api(list_of_dicts_list, fastapi_url="http://localhost:8000/api/your_endpoint") -> Tuple[
    int, int]:
    """
    Sends a list of lists containing JSON data to a FastAPI endpoint.

    Returns:
        Tuple[int, int]: A tuple containing the number of successful and failed sends.
    """
    # fastapi_url = "http://localhost:8000/api/your_endpoint"

    # list_of_dicts_list = [
    #     [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 40}],
    #     [{"name": "Charlie", "age": 50}, {"name": "David", "age": 60}]
    # ]

    successful_sends = 0
    failed_sends = 0

    for dicts_list in list_of_dicts_list:
        for data_dict in dicts_list:
            status_code = send_to_fastapi(data_dict, fastapi_url)

            if status_code == 200:
                print(f"Successfully sent {data_dict} to FastAPI endpoint.")
                logger.info(f"Successfully sent {data_dict} to FastAPI endpoint.")
                successful_sends += 1
            else:
                print(f"Failed to send {data_dict}. Status code: {status_code}")
                logger.error(f"Failed to send {data_dict}. Status code: {status_code}")
                failed_sends += 1

    return successful_sends, failed_sends


if __name__ == "__main__":
    token_testing = "TEST eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbiI6InRlc3RpbmciLCJpYXQiOjE"
    send_token_to_server(token_testing)