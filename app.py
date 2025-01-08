from flask import Flask, render_template, redirect, url_for, request, flash
from tests.manual_azure_trigger import scrape_pdfs_from_webpage, get_last_modified, download_and_process_pdf
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import os
import requests
from urllib.parse import quote, unquote

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For flash messages

# Azure SQL Database connection setup
def init_db_connection():
    server = os.getenv('DB_SERVER')
    database = os.getenv('DB_NAME')
    username = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    driver = '{ODBC Driver 18 for SQL Server}'
    
    conn = pyodbc.connect(f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}')
    cursor = conn.cursor()
    return conn, cursor

# Function to fetch status of each PDF from database by webpage_url
def fetch_url_status(webpage_url):
    conn, cursor = init_db_connection()
    print(f"Checking status for webpage URL: {webpage_url}")  # Debugging print
    cursor.execute("SELECT COUNT(*) FROM pdf_metadata WHERE webpage_url = ?", (webpage_url,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Function to fetch the latest modified PDF by webpage_url
def fetch_latest_pdf(webpage_url):
    conn, cursor = init_db_connection()
    print(f"Fetching latest PDF for webpage URL: {webpage_url}")  # Debugging print
    cursor.execute("SELECT TOP 1 file_name, last_modified, url FROM pdf_metadata WHERE webpage_url = ? ORDER BY last_modified DESC", (webpage_url,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result  # Includes file_name, last_modified, and download URL
    return None

def fetch_all_pdfs_for_url(webpage_url):
    conn, cursor = init_db_connection()
    print(f"Fetching all PDFs for webpage URL: {webpage_url}")  # Debugging print

    # Query to include the PDF URL (as 'download') along with other metadata
    cursor.execute(""" 
        SELECT file_name, last_modified, status, url AS download 
        FROM pdf_metadata 
        WHERE webpage_url = ? 
        ORDER BY last_modified DESC
    """, (webpage_url,))
    result = cursor.fetchall()
    conn.close()  # Ensure the connection is closed
    return result  # Return the fetched data

# Function to trigger scraping and process PDFs for a specific URL
def manual_trigger_for_url(webpage_url):
    pdf_links = scrape_pdfs_from_webpage(webpage_url)
    updates_found = False

    for pdf_url in pdf_links:
        file_name = pdf_url.split("/")[-1].split("?")[0]  # Extract the actual file name
        last_modified = get_last_modified(pdf_url)

        conn, cursor = init_db_connection()
        cursor.execute("SELECT id, last_modified FROM pdf_metadata WHERE url = ?", (pdf_url,))
        result = cursor.fetchone()

        if result:
            db_id, db_last_modified = result
            if last_modified and last_modified != db_last_modified:
                # Update metadata for modified PDFs
                download_and_process_pdf(pdf_url, file_name, last_modified, "updated")
                cursor.execute("UPDATE pdf_metadata SET last_modified = ?, status = 'updated' WHERE id = ?", 
                               (last_modified, db_id))
                conn.commit()
                updates_found = True
            else:
                # Mark unchanged PDFs
                cursor.execute("UPDATE pdf_metadata SET status = 'unchanged' WHERE id = ?", (db_id,))
                conn.commit()
        else:
            # Insert new PDFs into the database
            download_and_process_pdf(pdf_url, file_name, last_modified, "new")
            cursor.execute("""
                INSERT INTO pdf_metadata (webpage_url, url, file_name, last_modified, status)
                VALUES (?, ?, ?, ?, 'new')
            """, (webpage_url, pdf_url, file_name, last_modified))
            conn.commit()
            updates_found = True

        conn.close()

    return updates_found

URLs = [
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/criminal-court-forms",
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/prov-family-forms",
    "https://www2.gov.bc.ca/gov/content/justice/courthouse-services/documents-forms-records/court-forms/federal-contraventions-vt-forms"
]

@app.route('/')
def index():
    # Pass the URL indices to the template
    return render_template('index.html', urls=URLs)

@app.route('/monitor-url/<int:url_id>')
def monitor_url(url_id):
    url = URLs[url_id]
    
    # Fetch the latest modified PDF
    latest_pdf = fetch_latest_pdf(url)
    
    # Fetch all PDFs for the specific URL
    all_pdfs = fetch_all_pdfs_for_url(url)
    
    return render_template('monitor_url.html', 
                           url=url, 
                           latest_pdf=latest_pdf, 
                           all_pdfs=all_pdfs,  # Pass the fetched PDFs to the template
                           url_id=url_id)

@app.route('/manual-trigger/<int:url_id>', methods=['POST'])
def manual_trigger(url_id):
    url = URLs[url_id]  # Use the URL index
    updates_found = manual_trigger_for_url(url)
    
    if updates_found:
        flash('New or updated PDFs were found and processed.', 'success')
    else:
        flash('No new or updated PDFs were found.', 'info')
    
    return redirect(url_for('monitor_url', url_id=url_id))

if __name__ == '__main__':
    app.run(debug=True)
