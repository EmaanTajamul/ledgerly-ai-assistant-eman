# Ledgerly — E-Commerce Operations AI Assistant

Ledgerly is an AI assistant for e-commerce operations. Instead of letting an LLM guess numbers, it uses **LLM function calling**: Gemini chooses from 14 Python tools, FastAPI runs the matching function against a SQLite database, and the answer is written from the tool results.

> **Status:** learning project built on generated sample data. It is not production software and has no authentication or automated tests yet.

## How it works

1. A user asks a question in plain language, for example *"Compare June and July revenue"* or *"Which variants are close to stocking out?"*
2. The `/chat` endpoint sends the question and the tool schemas to Gemini through an OpenAI-compatible SDK.
3. Gemini picks one or more tools. The backend validates the arguments, runs the function, and returns the result to the model (up to 5 tool-calling rounds per question).
4. Gemini writes the final answer from the tool results.
5. Every tool call is saved to the `audit_logs` and `tool_runs` tables with its arguments, result, status, and duration.

## Tools (14)

| Type | Tools |
|---|---|
| Catalog and inventory | `search_products`, `get_product_details`, `get_inventory`, `get_stockout_risk`, `calculate_reorder_quantity` |
| Orders and customers | `get_order`, `get_customer_summary` |
| Sales analytics | `get_sales_summary`, `compare_sales_periods`, `get_product_performance`, `get_refund_summary` |
| External data | `get_exchange_rate` (PKR to USD/EUR/GBP via the Frankfurter API) |
| Proposals (human review) | `propose_discount`, `propose_inventory_alert` |

## Safety design

- **Read-only assistant.** There are no tools that modify business data.
- **Proposals, not actions.** Discounts and inventory alerts are suggestions only. `propose_inventory_alert` saves a pending request to `approval_requests` for human review.
- **Approval records a decision only.** `POST /approvals/{id}/review` marks a request approved or rejected. It never executes the underlying action.
- **Input validation.** Dates must be `YYYY-MM-DD`, limits are bounded, and all SQL is parameterized.
- **Structured errors.** Tool failures return error objects the model can handle, and unexpected exceptions do not leak internal details.

## Tech stack

Python, FastAPI, Pydantic, SQLite, Google Gemini API (via the OpenAI Python SDK, OpenAI-compatible endpoint), and a plain HTML/CSS/JavaScript frontend.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Ask a question; returns `{"answer": "..."}` |
| GET | `/approvals?status=pending` | List approval requests (`pending`, `approved`, `rejected`) |
| POST | `/approvals/{request_id}/review` | Approve or reject a pending request |
| GET | `/` | Web interface (served from `frontend/`) |

Interactive API docs are available at `/docs`.

## Project structure

```text
├── app.py              # FastAPI app, tool schemas, Gemini tool-calling loop, approval endpoints
├── main.py             # Database access, validation, and the 14 tool functions
├── check_db.py         # Prints an inventory summary from the database
├── check_tables.py     # Prints the approval_requests table schema
├── requirements.txt
└── frontend/
    ├── index.html
    ├── script.js
    └── style.css
```

## Setup

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Add your Gemini API key

Create a `.env` file in the project root:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
```

Never commit your real key. `.env` is already in `.gitignore`.

### 3. Add the database

The app expects a SQLite file named `ecommerce_generated.db` in the project root. It is excluded from version control and **is not included in this repository**, and a seed script has not been added yet.

The code expects these tables: `products`, `variants`, `inventory`, `customers`, `orders`, `order_items`, `refunds`, `approval_requests`, and `tool_runs`. The `audit_logs` table is created automatically on startup.

### 4. Run the app

```bash
uvicorn app:app --reload
```

Open http://127.0.0.1:8000 for the interface or http://127.0.0.1:8000/docs for the API docs.

## Known limitations and next steps

- Add a database schema and seed script so the project runs out of the box
- Add automated tests for the tools and endpoints
- Add read endpoints for `audit_logs` and `tool_runs` (they are written but not yet viewable in the UI)
- Add authentication and reviewer identity checks for the approval endpoints
- Pin dependency versions
- `calculate_reorder_quantity` is a simple threshold-based calculation, not demand forecasting
