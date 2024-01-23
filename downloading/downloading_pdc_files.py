import os
import json
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO)


class FileDownloader:
    def __init__(self, bearer_token_pdc):
        self.token_value = bearer_token_pdc

    def download_pdf(self, url, filename):
        headers = {"Authorization": self.token_value}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            pdf_info = response.json()
            pdf_url = pdf_info.get("url")
            if pdf_url:
                pdf_response = requests.get(pdf_url)
                pdf_response.raise_for_status()
                filename.write_bytes(pdf_response.content)
                return True
        except (requests.RequestException, json.JSONDecodeError) as e:
            logging.error(f"Failed to download PDF: {e}")
            return False


    def download_files(self, list_of_files, download_path=Path("./downloads")):
        download_path.mkdir(parents=True, exist_ok=True)

        for file in list_of_files:
            links = file.get("_links", {})
            file_id = links.get("self", {}).get("href", "").split("/")[-1]

            if not file_id:
                logging.warning("Skipping file due to missing '_links.self.href'")
                continue

            order_folder = download_path / file_id
            # order_folder.mkdir(exist_ok=True)

            for i, design in enumerate(file.get("designs", []), start=1):
                design_folder = Path(str(order_folder) + f"_{i}")
                design_folder.mkdir(exist_ok=True)

                design_url = design.get("href")
                if design_url and self.download_pdf(design_url, design_folder / f"{file_id}_design_{i}.pdf"):
                    logging.info(f"Design {i} for {file_id} downloaded to {design_folder}.")

                jobsheet_file_url = links.get("jobsheet", {}).get("href")
                if jobsheet_file_url and self.download_pdf(jobsheet_file_url,
                                                           design_folder / f"{file_id}_jobsheet_{i}.pdf"):
                    logging.info(f"Jobsheet file for {file_id} downloaded to {design_folder}.")


if __name__ == "__main__":
    token_value = "Your_Bearer_Token_Here"
    files = []  # Your list of list_of_files here

    # downloader = FileDownloader(token_value)
    # downloader.download_files(files)
    # enter cerm-json per design and zip the folder
    # add try except in download_pdf
    # send files to api and have api download them! so all customers can use this code to download their files.


