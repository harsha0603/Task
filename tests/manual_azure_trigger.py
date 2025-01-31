import requests
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import os
from bs4 import BeautifulSoup
import re
from dotenv import load_dotenv

# Azure Blob Storage setup
connection_string = "AZURE_BLOB_CONNECTION_STRING"
container_name = "AZURE_BLOB_CONTAINER"
blob_service_client = BlobServiceClient.from_connection_string("connection_string")
container_client = blob_service_client.get_container_client(container_name)

load_dotenv()

# Access your credentials securely
server = os.getenv('DB_SERVER')
database = os.getenv('DB_NAME')
username = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
driver = '{ODBC Driver 18 for SQL Server}'

# Establish connection to Azure SQL Database
conn = pyodbc.connect(f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}')
cursor = conn.cursor()

# Function to scrape PDFs from a webpage
def scrape_pdfs_from_webpage(webpage_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(webpage_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract raw URLs directly from the href attributes
        all_links = [a['href'] for a in soup.find_all('a', href=True)]

        # Filter only PDF links
        pdf_links = [link for link in all_links if re.search(r'\.pdf($|\?)', link)]

        print(f"Found {len(pdf_links)} PDFs on {webpage_url}")
        return pdf_links
    except Exception as e:
        print(f"Error scraping {webpage_url}: {e}")
        return []

# Function to fetch 'Last-Modified' header
def get_last_modified(pdf_url):
    try:
        response = requests.head(pdf_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        return response.headers.get('Last-Modified', None)
    except Exception as e:
        print(f"Error fetching Last-Modified for {pdf_url}: {e}")
        return None

# Function to fetch all PDFs metadata for a specific URL in one query
def fetch_all_metadata_for_url(webpage_url):
    cursor.execute("""
        SELECT id, file_name, last_modified, webpage_url 
        FROM pdf_metadata 
        WHERE webpage_url = ?
    """, (webpage_url,))
    return cursor.fetchall()

import os
import re

# Helper function to normalize the PDF file name
def normalized_filename(url):
    # Extract file name from the URL and normalize it
    file_name = os.path.basename(url).split('?')[0]  # Remove query parameters if any
    return re.sub(r'[\\/*?:"<>|]', "_", file_name)  # Sanitize file name

import pyodbc

def process_pdfs(pdf_links, webpage_url):
    # Azure SQL Database connection setup
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 18 for SQL Server}};'
                          f'SERVER={server};PORT=1433;DATABASE={database};'
                          f'UID={username};PWD={password}')
    cursor = conn.cursor()

    for pdf_url in pdf_links:
        file_name = pdf_url.split("/")[-1].split("?")[0]  # Extract the actual file name
        last_modified = get_last_modified(pdf_url)

        # Check if the PDF already exists in the database by URL
        cursor.execute("SELECT id, last_modified FROM pdf_metadata WHERE url = ?", (pdf_url,))
        result = cursor.fetchone()

        if result:
            # Existing PDF - check if updated
            db_id, db_last_modified = result
            if last_modified and last_modified != db_last_modified:
                print(f"Updated PDF detected: {file_name}")
                download_and_process_pdf(pdf_url, file_name, last_modified, "updated", cursor, conn)
            else:
                print(f"No changes for: {file_name}")
        else:
            # New PDF detected
            print(f"New PDF detected: {file_name}")
            download_and_process_pdf(pdf_url, file_name, last_modified, "new", cursor, conn)

    # Close the connection after processing
    cursor.close()
    conn.close()

# Function to download, upload, and store metadata
def download_and_process_pdf(pdf_url, file_name, last_modified, status):
    try:
        sanitized_file_name = re.sub(r'[\\/*?:"<>|]', "_", file_name)

        # Download PDF
        response = requests.get(pdf_url, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        with open(sanitized_file_name, "wb") as pdf_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    pdf_file.write(chunk)
        print(f"Downloaded {sanitized_file_name}")

        # Upload to Azure Blob
        blob_client = container_client.get_blob_client(sanitized_file_name)
        with open(sanitized_file_name, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{sanitized_file_name}"
        print(f"Uploaded to Azure Blob: {blob_url}")

        # Store metadata in Azure SQL Database
        size = os.path.getsize(sanitized_file_name)
        cursor.execute(''' 
            INSERT INTO pdf_metadata (file_name, url, blob_url, last_modified, download_date, size, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sanitized_file_name, pdf_url, blob_url, last_modified or '', datetime.now().isoformat(), size, status))
        conn.commit()

        # Clean up local file
        os.remove(sanitized_file_name)

    except Exception as e:
        print(f"Error processing {file_name}: {e}")

# Main manual trigger function
def manual_trigger():
    webpages = [
        "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/criminal-court-forms",
        "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/prov-family-forms",
        "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/federal-contraventions-vt-forms"
    ]

    for webpage_url in webpages:
        print(f"Processing webpage: {webpage_url}")
        pdf_links = scrape_pdfs_from_webpage(webpage_url)
        process_pdfs(pdf_links, webpage_url)

# Run the manual trigger
if __name__ == "__main__":
    manual_trigger()

    # Close the database connection after processing
    cursor.close()
    conn.close()
