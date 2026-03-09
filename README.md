# FASTR App

A web application with a FastAPI backend and a React (Vite) frontend.

## Prerequisites

Before you begin, ensure you have the following installed on your machine:
- [Git](https://git-scm.com/)
- [Node.js](https://nodejs.org/) (v16 or higher recommended)
- [Python](https://www.python.org/) 3.11+
- [Oracle Wallet / Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client.html) (if connecting to an Oracle DB locally)

## Setup Instructions for a New PC

### 1. Clone the Repository

Clone the project from GitHub and navigate into the directory:

```bash
git clone https://github.com/ashwsrin/fastr_app.git
cd fastr_app
```

### 2. Set Up the Backend

The backend is a FastAPI application that requires its own virtual environment.

```bash
# Navigate to the backend directory
cd backend

# Create a Python virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# .\venv\Scripts\activate

# Install the required Python packages
pip install -r requirements.txt

# Create an implementation of the .env file
cp .env.example .env
```
*Note: Make sure to fill in the correct credentials in the new `.env` file! The app will need `OPENAI_API_KEY`, Oracle DB credentials, etc.*

### 3. Set Up the Frontend

The frontend is a React application powered by Vite.

```bash
# Open a NEW terminal window/tab
# Navigate back to the project root and then to the frontend directory
cd frontend

# Install Node.js dependencies
npm install
```

---

## Running the Application Locally

You will need to run the backend and frontend in two separate terminal windows.

### Start the Backend Server

```bash
# Navigate to the backend directory
cd backend

# Activate the virtual environment if it isn't already active
source venv/bin/activate # (macOS/Linux)
# .\venv\Scripts\activate (Windows)

# Run the FastAPI server
uvicorn main:app --reload
```
The backend API will be available at `http://127.0.0.1:8000`.

### Start the Frontend Server

```bash
# Open a separate terminal window and navigate to the frontend directory
cd frontend

# Start the React Vite development server
npm run dev
```
The frontend UI will be available at `http://localhost:5173`. Open this URL in your web browser to use the application.
