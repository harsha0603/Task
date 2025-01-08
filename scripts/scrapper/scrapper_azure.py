import os
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import pyodbc
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Azure SQL setup
def init_azure_sql_connection():
    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DATABASE")
    username = os.getenv("AZURE_SQL_USERNAME")
    password = os.getenv("AZURE_SQL_PASSWORD")

    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password}'
    )
    cursor = conn.cursor()
    return conn, cursor

# Azure Blob Storage setup
connection_string = os.getenv("AZURE_BLOB_CONNECTION_STRING")
container_name = os.getenv("AZURE_BLOB_CONTAINER")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# Function to check if PDF already exists in Azure Blob Storage
def pdf_exists_in_blob(blob_name):
    try:
        blob_client = container_client.get_blob_client(blob_name)
        # Check if blob exists by trying to fetch its properties
        blob_client.get_blob_properties()
        return True  # Blob exists
    except Exception as e:
        return False  # Blob does not exist

# Function to check if metadata already exists in Azure SQL Database
def metadata_exists_in_db(pdf_url, cursor):
    cursor.execute("SELECT 1 FROM pdf_metadata WHERE url = ?", (pdf_url,))
    return cursor.fetchone() is not None

# Function to download PDF from URL
def download_pdf(pdf_url, local_filename):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Accept": "application/pdf"
        }
        response = requests.get(pdf_url, headers=headers, stream=True, allow_redirects=True)
        if response.status_code == 200:
            with open(local_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            print(f"PDF downloaded successfully to {local_filename}")
            return True
        else:
            print(f"Failed to download PDF. HTTP status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False

# Function to upload PDF to Azure Blob Storage
def upload_pdf_to_blob(local_filename, blob_name):
    try:
        blob_client = container_client.get_blob_client(blob_name)
        with open(local_filename, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"File uploaded successfully to Azure Blob Storage: {blob_name}")
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        return blob_url
    except Exception as e:
        print(f"Error uploading PDF to Azure: {e}")
        return None

# Function to extract metadata from the PDF
def extract_metadata(local_filename):
    try:
        metadata = {
            "file_name": local_filename,
            "size": os.path.getsize(local_filename),
            "last_modified": datetime.now().isoformat(),  # We'll update this after fetching actual 'Last-Modified'
            "download_date": datetime.now().isoformat(),
            "status": "new"
        }
        print(f"Metadata extracted: {metadata}")
        return metadata
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return None

# Function to store metadata in Azure SQL
def store_metadata(metadata, cursor, conn):
    try:
        cursor.execute('''
            INSERT INTO pdf_metadata (file_name, url, blob_url, last_modified, download_date, size, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (metadata['file_name'], metadata['url'], metadata['blob_url'], metadata['last_modified'], 
              metadata['download_date'], metadata['size'], metadata['status']))
        conn.commit()
        print(f"Metadata stored in Azure SQL: {metadata}")
    except Exception as e:
        print(f"Error storing metadata: {e}")

# Function to scrape PDFs from a given webpage URL
def scrape_pdfs_from_webpage(webpage_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(webpage_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        all_links = [a['href'] for a in soup.find_all('a', href=True)]
        pdf_links = [link for link in all_links if re.search(r'\.pdf($|\?)', link)]
        pdf_links = [requests.compat.urljoin(webpage_url, link) for link in pdf_links]
        print(f"Found {len(pdf_links)} PDFs on {webpage_url}")
        return pdf_links
    except Exception as e:
        print(f"Error scraping {webpage_url}: {e}")
        return []

# Function to fetch the 'Last-Modified' header
def get_last_modified(pdf_url, retries=3, delay=5):
    """
    Attempt to fetch the 'Last-Modified' header from a PDF URL with retry logic.
    """
    for attempt in range(retries):
        try:
            response = requests.get(pdf_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()  # Raise an error for bad HTTP responses
            last_modified = response.headers.get('Last-Modified', 'Unknown')
            return last_modified
        except Exception as e:
            print(f"Error fetching Last-Modified for {pdf_url}: {e}")
            if attempt < retries - 1:
                print(f"Retrying ({attempt+1}/{retries})...")
                time.sleep(delay)  # Wait before retrying
            else:
                print(f"Failed after {retries} attempts for {pdf_url}.")
                return None

# Scrape the pages for different URLs
webpage_urls = [
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/criminal-court-forms",
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/prov-family-forms",
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/federal-contraventions-vt-forms"
]

# Initialize Azure SQL connection and Azure Blob Storage
conn, cursor = init_azure_sql_connection()

# Process each website
for webpage_url in webpage_urls:
    pdf_links = scrape_pdfs_from_webpage(webpage_url)

    # Process each PDF found on the page
    for pdf_url in pdf_links:
        file_name = pdf_url.split("/")[-1].split("?")[0]  # Extract the actual file name from the URL
        local_filename = f"{file_name}"

        # Step 1: Check if PDF already exists in Azure Blob Storage
        if pdf_exists_in_blob(file_name):
            print(f"PDF already exists in Azure Blob Storage: {file_name}")
        else:
            print(f"PDF not found in Azure Blob Storage: {file_name}")
            # Step 2: Mock downloading (Do not download)
            print(f"Mock downloading PDF: {pdf_url}")

        # Step 3: Check if metadata already exists in Azure SQL
        if metadata_exists_in_db(pdf_url, cursor):
            print(f"Metadata for {file_name} already exists in the database.")
        else:
            print(f"Metadata for {file_name} does not exist in the database.")
            # Step 4: Mock storing metadata (Do not actually store)
            metadata = {
                'file_name': file_name,
                'url': pdf_url,
                'blob_url': 'mock_blob_url',  # You can mock the blob URL for testing
                'last_modified': 'mock_last_modified',  # Mock last_modified date
                'download_date': datetime.now().isoformat(),
                'size': 12345,  # Mock file size
                'status': 'new'
            }
            print(f"Mock storing metadata: {metadata}")
        
        # Clean up (no need to delete any files since we're not downloading/uploading)
        print(f"Skipping file cleanup for {file_name}")

# Close the database connection
conn.close()
