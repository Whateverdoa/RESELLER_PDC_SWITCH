import logging
import time
import requests
import sqlite3
import json
from datetime import datetime
import os
from dotenv import load_dotenv

from extract_from_sql.sqlite_extract import collect_orders_from_database, fetch_order_items_for_update, \
    update_order_items_status
from downloading.downloading_pdc_files import FileDownloader
from orders_to_vila_fast_api.send_to_vila_fast_api import send_token_to_server
from paden.pad import log_pad

load_dotenv()

logging.basicConfig(level=logging.INFO,filename=log_pad, format="%(asctime)s [%(levelname)s]: %(message)s")
logging.info("Logging initialized")

class PrintDotComAPI:
    def __init__(self, eagle_user, eagle_password, environment):
        self.eagle_user = eagle_user
        self.eagle_password = eagle_password
        self.environment = environment
        self.token_value = ""
        self.token_valid = 0
        # self.setup_logging()

    # @staticmethod
    # def setup_logging():
    #     """Set up logging."""
    #     logging.basicConfig(level=logging.INFO,filename=log_pad, format="%(asctime)s [%(levelname)s]: %(message)s")
    #     logging.info("Logging initialized")

    def authenticate(self):
        """Authenticate and get JWT Bearer token."""
        login_url = (
            "https://eagerapi.print.beer/login" if self.environment == "Test" else "https://eagerapi.print.com/login"
        )
        try:
            response = requests.post(
                login_url,
                auth=(self.eagle_user, self.eagle_password),
            )
            response.raise_for_status()
            token = response.text
            self.token_value = "Bearer " + token.strip('\"')
            # print(self.token_value)
            self.token_valid = int((datetime.now().timestamp())) + 3600  # 1 hour validity
            logging.info("Successfully authenticated")
        except requests.RequestException as e:
            logging.error(f"Authentication failed: {e}")
            self.token_value = ""
            self.token_valid = 0

    def make_request(self, url, method="GET", headers=None, payload=None):
        """Make an HTTP request and return the response."""
        if headers is None:
            headers = {}
        headers["Authorization"] = self.token_value

        response = None  # Initialize to None

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=payload)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"HTTP request failed: {e}")
            return None
        except ValueError as e:
            logging.error(e)
            return None

    def update_job_status_with_message(self, item_id, new_status, message=""):
        """Update the status of a specific job by its orderItemNumber and add a message."""

        # Construct the comment body
        comment_body = {
            "status": new_status,
            "username": self.eagle_user,
            "message": message if message else f"Updated by user {self.eagle_user}"
        }

        # Prepare the API request
        api_url = (
            f"https://eagerapi.print.beer/order-items/{item_id}/status"
            if self.environment == "Test"
            else f"https://eagerapi.print.com/order-items/{item_id}/status"
        )
        # print(self.token_value)
        headers = {"Accept": "application/json", "Authorization": self.token_value}
        post_data = {"status": new_status, "comment": comment_body}

        response = requests.post(api_url, headers=headers, json=post_data)
        request_successful = response.status_code == 200


        if request_successful:
            logging.info(f"Successfully updated order item {item_id} to status {new_status}.")
            return True
        else:
            logging.error(f"Unable to set status to {new_status} for {item_id}.")
            return False

    def fetch_and_store_jobs_(self, status="SENTTOSUPPLIER"):
        """Fetch jobs based on a given status and store them in SQLite database."""
        url = (
            f"https://eagerapi.print.beer/order-items/?statuses={status}"
            if self.environment == "Test"
            else f"https://eagerapi.print.com/order-items/?statuses={status}"
        )

        # Fetch jobs from API
        jobs = self.make_request(url)

        if self.environment != "Test":
            db = "jobs_eager.db"
        else:
            db = "jobs.db"

        # Store jobs in SQLite database
        if jobs:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    order_item TEXT,
                    full_order TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            inserted_jobs = []

            for job in jobs:
                job_status = job.get("status", "")
                job_order_item = job.get("orderItemNumber", "")

                # Check if the order_item already exists in the database
                cursor.execute(
                    "SELECT id, status FROM jobs WHERE order_item = ?",
                    (job_order_item,),
                )
                existing_order = cursor.fetchone()

                if existing_order:
                    # Order already exists in the database
                    existing_status = existing_order[1]
                    if existing_status != "ALREADY_RECEIVED_BY_VILA":
                        # Update the status to "ALREADY_RECEIVED_BY_VILA" if it's not already set
                        cursor.execute(
                            "UPDATE jobs SET status = ? WHERE id = ?",
                            ("ALREADY_RECEIVED_BY_VILA", existing_order[0]),
                        )
                        logging.info(
                            f"Updated status for order {job_order_item} to ALREADY_RECEIVED_BY_VILA"
                        )
                else:
                    # Order doesn't exist in the database, insert it
                    inserted_jobs.append(job)
                    job_str = json.dumps(job)
                    cursor.execute(
                        "INSERT INTO jobs (status, order_item, full_order) VALUES (?, ?, ?)",
                        (job_status, job_order_item, job_str),
                    )

            conn.commit()
            conn.close()
            logging.info(f"Successfully stored {len(jobs)} jobs in the database.")
            return inserted_jobs
        else:
            logging.warning("No jobs fetched from the API.")
            return []

    def fetch_and_store_jobs(self, status="SENTTOSUPPLIER"):
        """Fetch jobs based on a given status and store them in SQLite database."""
        url = (
            f"https://eagerapi.print.beer/order-items/?statuses={status}"
            if self.environment == "Test"
            else f"https://eagerapi.print.com/order-items/?statuses={status}"
        )

        # Fetch jobs from API
        jobs = self.make_request(url)

        if self.environment != "Test":
            db = "jobs_eager.db"
        else:
            db = "jobs.db"

        # Store jobs in SQLite database
        if jobs:
            conn = sqlite3.connect(db)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    order_item TEXT,
                    full_order TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            for job in jobs:
                job_status = job.get("status", "")
                job_order_item = job.get("orderItemNumber", "")
                job_str = json.dumps(job)
                cursor.execute(
                    "INSERT INTO jobs (status, order_item, full_order) VALUES (?, ?, ?)",
                    (job_status, job_order_item, job_str),
                )

            conn.commit()
            conn.close()
            logging.info(f"Successfully stored {len(jobs)} jobs in the database.")
            return jobs
        else:
            logging.warning("No jobs fetched from the API.")
            return []




    # this is not used, module downloading_pdc_files is used
    def download_files(self, files, download_path="./downloads"):
        """
        Downloads jobsheets and production files for a list of files.

        Args:
            files (list): List of dictionaries containing file information.
            download_path (str): Directory where the downloaded files will be stored.

        Returns:
            None
        """

        def download_pdf_bearer(url, filename):
            headers = {"Authorization": self.token_value}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                response_data = json.loads(response.text)
                pdf_url = response_data["url"]
                pdf_response = requests.get(pdf_url)
                if pdf_response.status_code == 200:
                    with open(filename, "wb") as file:
                        file.write(pdf_response.content)

                    return f"PDF downloaded and saved as {filename}"
                else:
                    return "Failed to download the PDF from the provided URL"
            else:
                return "Failed to download the PDF"

        def download_pdf(url, filename):
            headers = {"Authorization": self.token_value}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                try:
                    pdf_info = json.loads(response.text)  # Deserialize JSON
                    pdf_url = pdf_info.get("url", None)  # Extract actual PDF URL
                    if pdf_url:
                        pdf_response = requests.get(pdf_url)
                        if pdf_response.status_code == 200:
                            with open(filename, "wb") as file:
                                file.write(pdf_response.content)
                            return True
                        else:
                            return False
                    else:
                        return False
                except json.JSONDecodeError:
                    return False
            else:
                return False

        if not os.path.exists(download_path):
            os.makedirs(download_path)

        for file in files:
            links = file.get("_links", {})
            if "self" not in links or "href" not in links["self"]:
                print("Skipping file due to missing '_links.self.href'")
                continue

            file_id = links["self"]["href"].split("/")[-1]  # Extracting unique identifier
            order_folder = os.path.join(download_path, file_id)
            print(f'{order_folder} {file_id}')

            if not os.path.exists(order_folder):
                os.makedirs(order_folder)

            designs = file.get("designs", [])
            for i, design in enumerate(designs):
                design_url = design.get("href")
                if design_url and download_pdf_bearer(
                        design_url,
                        f"{order_folder}/{file_id}_design_{i + 1}.pdf"

                ):
                    print(f"Design {i + 1} for {file_id} downloaded.")

            production_file_url = links.get("productionFile", {}).get("href")
            if production_file_url and download_pdf_bearer(
                    production_file_url,
                    f"{order_folder}/{file_id}_production_file.pdf",

            ):
                print(f"Production file for {file_id} downloaded.")

    def is_token_valid(self):
        """Check if the token is still valid."""
        return self.token_valid > int(datetime.now().timestamp())

    # def get_jobs(self):
    #     """Get a list of jobs from the print.com API."""
    #     pass
    #
    # def handle_received_print_job(self, print_job):
    #     """Handle a received print job."""
    #     pass
    #
    # def save_to_db(self, job_data):
    #     """Save parsed job data to an SQLite database."""
    #     pass


def main():

    # environment = "Test"  # or "Production"
    # Initialize the class
    # test
    # usertest = os.getenv("username3")
    # passwordtest = os.getenv("password3")
    # apitest = PrintDotComAPI(eagle_user=usertest, eagle_password=passwordtest, environment="Test")
    # urlABR = os.getenv("url_items_test2")
    # apitest.authenticate()

    eagle = os.getenv("username_eagle")
    password = os.getenv("password")
    print(eagle, password)
    api_real = PrintDotComAPI(eagle_user=eagle, eagle_password=password, environment="Real")
    api_real.authenticate()

    # Placeholder calls (to be implemented)
    # apitest.setup_logging()
    # api_real.setup_logging()

    # jobdata = apitest.make_request(urlABR)

    # apitest.fetch_and_store_jobs("ACCEPTEDBYSUPPLIER")
    # api_real.fetch_and_store_jobs()  # status default = senttosupplier

    # jobs = api.get_jobs()
    # for job in jobs:
    #     api.handle_received_print_job(job)

    # Initialize the class
    poll_interval = 250

    while True:
        # Check if token is valid, authenticate if not
        # if not apitest.is_token_valid():
        #     apitest.authenticate()
        send_token_to_server(api_real.token_value)
        if not api_real.is_token_valid():
            api_real.authenticate()
            send_token_to_server(api_real.token_value)

        # Fetch and store jobs
        # print(apitest.fetch_and_store_jobs(status="ACCEPTEDBYSUPPLIER"))
        # print(apitest.fetch_and_store_jobs(status="REFUSEDBYSUPPLIER"))

        # api_real.fetch_and_store_jobs()  # status default = senttosupplier

        # Download files ####
        # apitest.download_files(apitest.fetch_and_store_jobs(status="ACCEPTEDBYSUPPLIER"))

        # api_real.download_files(api_real.fetch_and_store_jobs())
        list_of_files_ = api_real.fetch_and_store_jobs()

        # if list!=None: # if list is not empty then send list of files to vilaapi
        if list_of_files_:
            send_token_to_server(api_real.token_value)
            # dl = FileDownloader(token_value)
            # dl.download_files(list_of_files_, DOWNLOAD_PAD)
            # print(list_of_files_)
            print("collect orders from database")
            print('_-'*50)

            # after downloading the files send the order to the api for cerm_json and zipping
            # added ACCEPTEDBYSUPPLIER temp for shadowrun
            collect_orders_from_database(api_real)

            ########status change temp
            # db_path = "jobs_eager.db"  # Replace with the actual path to your database
            # status_to_fetch = "ORDERRECEIVEDBYVILA"  # Replace with the actual status you want to fetch
            # new_status = "ACCEPTEDBYSUPPLIER"  # The new status you want to set
            # message = ""  # Your custom message
            #
            # # Fetch order items
            # order_items_to_update = fetch_order_items_for_update(db_path, status_to_fetch)
            #
            # # Update the status of each order item
            # update_order_items_status(api_real, order_items_to_update, new_status, message)


        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
