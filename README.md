\# Ledgerly — E-Commerce Operations AI Assistant



Ledgerly is an AI-powered assistant that helps manage e-commerce operations using natural-language questions and AI tool calling.



\## Features



\- Ask questions about sales, orders, inventory, refunds, and product performance.

\- Use AI tool calling to connect natural-language requests with backend operations.

\- Build REST APIs using FastAPI and Pydantic.

\- Store e-commerce data in SQLite.

\- Provide a web interface using HTML, CSS, and JavaScript.



\## Tech Stack



\- Python

\- FastAPI

\- Google Gemini API

\- OpenAI-compatible Python SDK

\- SQLite

\- Pydantic

\- HTML

\- CSS

\- JavaScript



\## Project Structure



```text

ecommerce-ai-assistant/

├── app.py

├── main.py

├── check\_db.py

├── check\_tables.py

├── requirements.txt

├── .gitignore

└── frontend/

&#x20;   ├── index.html

&#x20;   ├── script.js

&#x20;   └── style.css

```



\## Setup



\### 1. Install Dependencies



Install Python dependencies using:



```powershell

python -m pip install -r requirements.txt

```



\### 2. Configure the API Key



Create a `.env` file in the project root and add your Gemini API key:



```dotenv

GEMINI\_API\_KEY=your\_gemini\_api\_key

```



Replace `your\_gemini\_api\_key` with your own API key. Do not share or upload your real key.



\### 3. Run the Application



Start the FastAPI server:



```powershell

uvicorn app:app --reload

```



Open the API documentation in your browser:



http://127.0.0.1:8000/docs



\## Security



\- API credentials are stored in environment variables.

\- The `.env` file must not be uploaded to GitHub.

\- Virtual environments and private database files are excluded from version control.



\## Project Status



This project is under development.



