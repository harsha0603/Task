# Website Monitoring System for PDF Detection

This project is a **website monitoring system** designed to detect new or updated PDFs from a target website. It scrapes data from the website, processes it, and stores the metadata in an Azure SQL Database. The results are displayed on a dynamic dashboard built using Flask. The project is fully containerized with Docker for ease of deployment and scalability.

## Features
- Detects new or updated PDFs on a target website.
- Extracts metadata from the PDFs and stores it in a database(Azure)
- Actual PDFs are stored in Azure Blob Storage
- Provides a dynamic dashboard to view:
  - Newly detected PDFs.
  - Quantifiable metrics, such as the count of new PDFs.
- Containerized using Docker for easy setup and deployment.
---

## Prerequisites
- Python 3.11+
- Docker installed on your system.
- An Azure account to set up the Azure SQL Database.
- Access to the target website you want to monitor.

## Table of Contents

- [Technologies Used](#technologies-used)
- [Setup Instructions](#setup-instructions)
  - [Setting up Azure SQL Database](#setting-up-azure-sql-database)
  - [Cloning the Repository](#cloning-the-repository)
  - [Setting up the Environment](#setting-up-the-environment)
  - [Running the Docker Image](#running-the-docker-image)
  - [Accessing the Dashboard](#accessing-the-dashboard)
  - [Running the Application with Docker Compose](#running-the-application-with-docker-compose)
- [CI/CD Pipeline Setup](#cicd-pipeline-setup)
- [Troubleshooting](#troubleshooting)

---

## Technologies Used

- **Python** (Flask)
- **Docker** (Containerization)
- **Azure SQL Database** (Data Storage)
- **Azure Blob Storage** (PDF Storage)
- **GitHub Actions** (CI/CD Pipeline)
- **pyodbc** (SQL Server Connectivity)
- **requests**, **BeautifulSoup** (Web Scraping)

---

## Setup Instructions

Follow the steps below to set up and run the project.

### Setting up Azure SQL Database

1. **Create an Azure Account**:
   - If you don’t have an Azure account, create one at [Azure Portal](https://portal.azure.com/).

2. **Create an Azure SQL Database**:
   - Navigate to the **SQL Databases** section in the Azure portal.
   - Click **Add** to create a new SQL Database.
   - Choose a **Subscription** and **Resource Group** or create new ones.
   - Name your database and choose a **Server**. If you don’t have a server, create a new one (provide a unique name and credentials).
   - Set the pricing tier and complete the database creation.

3. **Get Database Connection String**:
   - After the database is created, navigate to the **Overview** page of your SQL Database.
   - Under **Connection Strings**, select **ADO.NET** or **ODBC** to copy the connection string. This will be used in your `.env` file to configure database connectivity.

4. **Configure Firewall**:
   - Go to the **Firewalls and Virtual Networks** tab and add your IP address to allow the connection to the database.

---

### Cloning the Repository

1. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/harsha0603/Task.git
   cd your-repository
   ```

### Setting up the Environment
1. Create a .env file in the project root:

# Azure SQL Credentials
```bash
DB_SERVER = YOUR_DATA_BASE_SERVER
DB_NAME = YOUR_DATA_BASE_NAME
DB_USER = USER_NAME
DB_PASSWORD = PASSWORD
FLASK_SECRET_KEY = your_secret_key
FLASK_APP = app.py
FLASK_ENV = development

# Azure Blob Storage Credentials
AZURE_BLOB_CONNECTION_STRING = STRING
AZURE_BLOB_CONTAINER = NAME OF CONTAINER
```
## Running the Docker Image
 
1. Build the Docker image:
```bash
docker build -t Task:latest .
```
2. Run the Docker container:
```bash
docker run -p 5000:5000 Task-app:latest
```
3. Access the application at:
``` bash
http://localhost:5000
```
### CI/CD Pipeline Setup

## This project uses GitHub Actions to automate the CI/CD process.

# Prerequisites
A DockerHub account for storing the built Docker images.
Steps
Add secrets to your GitHub repository:

Navigate to Settings > Secrets and variables > Actions.
Add the following secrets:
```bash DOCKER_USERNAME: Your DockerHub username.
DOCKER_PASSWORD: Your DockerHub password.
```
The GitHub Actions workflow file is located at .github/workflows/docker-build.yml.

# Workflow Steps
1. Checkout Code: Pulls the code from the repository.
2. Login to DockerHub: Logs into DockerHub using the provided secrets.
3. Build and Push Docker Image: Builds the Docker image and pushes it to DockerHub.
4. The workflow is triggered on every push or pull request to the main branch.

