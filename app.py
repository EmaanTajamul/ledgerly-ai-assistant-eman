import json
import os
from openai import APIStatusError

from openai import OpenAI, InternalServerError
from fastapi import FastAPI
from pydantic import BaseModel
import time
import uuid
from fastapi import HTTPException
from main import get_connection, save_tool_run
import os
from dotenv import load_dotenv

load_dotenv()

from main import (
    search_products,
    get_product_details,
    get_inventory,
    get_order,
    get_customer_summary,
    get_sales_summary,
    compare_sales_periods,
    get_product_performance,
    get_refund_summary,
    get_stockout_risk,
    get_exchange_rate,
    calculate_reorder_quantity,
    propose_discount,
    propose_inventory_alert,
    create_audit_logs_table,
save_audit_log,
)


app = FastAPI()
create_audit_logs_table()


class ChatRequest(BaseModel):
    question: str

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
# Tool schemas: descriptions and parameters available to Gemini.
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search products by name or keyword and optionally category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Get detailed information about a product using its product ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory",
            "description": "Get inventory information for a product variant using its variant ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variant_id": {"type": "integer"},
                },
                "required": ["variant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Retrieve order information using an order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_summary",
            "description": "Retrieve a customer summary using their customer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "integer"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Summarize ecommerce sales between two dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sales_periods",
            "description": "Compare sales across two date ranges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_start_date": {"type": "string"},
                    "first_end_date": {"type": "string"},
                    "second_start_date": {"type": "string"},
                    "second_end_date": {"type": "string"},
                },
                "required": [
                    "first_start_date",
                    "first_end_date",
                    "second_start_date",
                    "second_end_date",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_performance",
            "description": "Get product performance for a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refund_summary",
            "description": "Summarize refunds for a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stockout_risk",
            "description": "Find inventory variants at risk of running out of stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "Retrieve the exchange rate for a currency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {"type": "string"},
                },
                "required": ["currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_reorder_quantity",
            "description": "Calculate reorder quantity for a product variant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variant_id": {"type": "integer"},
                },
                "required": ["variant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_discount",
            "description": "Propose a discount for a product and explain the reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "discount_percent": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "product_id",
                    "discount_percent",
                    "reason",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_inventory_alert",
            "description": "Propose an inventory alert for a product variant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variant_id": {"type": "integer"},
                },
                "required": ["variant_id"],
            },
        },
    },
]


# Connect each tool name to its Python function.
available_functions = {
    "search_products": search_products,
    "get_product_details": get_product_details,
    "get_inventory": get_inventory,
    "get_order": get_order,
    "get_customer_summary": get_customer_summary,
    "get_sales_summary": get_sales_summary,
    "compare_sales_periods": compare_sales_periods,
    "get_product_performance": get_product_performance,
    "get_refund_summary": get_refund_summary,
    "get_stockout_risk": get_stockout_risk,
    "get_exchange_rate": get_exchange_rate,
    "calculate_reorder_quantity": calculate_reorder_quantity,
    "propose_discount": propose_discount,
    "propose_inventory_alert": propose_inventory_alert,
}


def ask_shop(question):
    request_id = str(uuid.uuid4())
    tool_history = []

    # Your existing code continues below
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are an ecommerce operations assistant. "
                "All money amounts (prices, revenue, refunds) are in Pakistani rupees (PKR). "
                "Write them as PKR, never as dollars. "
                "Use the available tools for product searches, product details, "
                "inventory, orders, customer summaries, sales summaries, "
                "sales comparisons, product performance, refunds, stockout risk, "
                "exchange rates, reorder quantities, discount proposals, "
                "and inventory alert proposals. "
                "Base answers on actual tool results. "
                "Never invent database information. "
                "Treat discount and inventory alerts as proposals, not actions "
                "that have already been applied."
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    # Allow up to five rounds of tool calling.
    for step in range(5):
        response = client.chat.completions.create(
            model="gemini-3.7-flash",
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or "No answer was returned."

        # Preserve the assistant's tool-call message.
        messages.append(message.model_dump(exclude_none=True))

        for call in message.tool_calls:
            function_name = call.function.name
            start_time = time.perf_counter()
            status = "success"
            arguments = {}

            try:
                arguments = json.loads(
                    call.function.arguments or "{}"
                )

                if function_name in available_functions:
                    result = available_functions[function_name](
                        **arguments
                    )
                else:
                    result = {"error": "Unknown tool requested."}

            except (json.JSONDecodeError, TypeError, ValueError) as error:
              result = {"error": str(error)}
              status = "error"

            
            except Exception:
                # Avoid exposing internal database or server details.
                result = {"error": "The requested tool failed internally."}
                status = "error"

            
            duration_ms = (time.perf_counter() - start_time) * 1000

            try:
                save_audit_log(
                    request_id=request_id,
                    tool_name=function_name,
                    arguments=arguments,
                    result=result,
                    duration_ms=duration_ms,
                    status=status,
                )
            except Exception as error:
                print(f"Audit logging failed: {error}")

            try:
                save_tool_run(
                    request_id=request_id,
                    tool=function_name,
                    arguments=arguments,
                    duration_ms=duration_ms,
                    status=status,
                    result=result,
                    error_message=(
                        result.get("error")
                        if isinstance(result, dict) and status == "error"
                        else None
                    ),
                )
            except Exception as error:
                print(f"Tool run logging failed: {error}")

            # Always send the tool result back to the AI.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                }
            )

    return "The assistant stopped after five tool-calling rounds."

           
@app.get("/approvals")
def list_approvals(status: str = "pending"):
    """List approval requests, pending by default."""
    allowed_statuses = {"pending", "approved", "rejected"}

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Status must be pending, approved, or rejected",
        )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT request_id, action, payload, status,
                   requester, reviewer, requested_at, reviewed_at
            FROM approval_requests
            WHERE status = ?
            ORDER BY requested_at DESC
            """,
            (status,),
        ).fetchall()

        results = []

        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload"])
            except (json.JSONDecodeError, TypeError):
                item["payload"] = {"raw": item["payload"]}

            results.append(item)

        return {"count": len(results), "approvals": results}

    finally:
        connection.close()


class ApprovalReview(BaseModel):
    decision: str
    reviewer: str

class ChatRequest(BaseModel):
    question: str


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        answer = ask_shop(request.question)
        return {"answer": answer}
    except Exception as error:
        print(f"Chat endpoint error: {error}")
        raise HTTPException(
            status_code=500,
            detail="The chat request failed."
        )


@app.post("/approvals/{request_id}/review")
def review_approval(request_id: int, review: ApprovalReview):
    """Approve or reject a pending request; never execute its action."""
    decision = review.decision.strip().lower()
    reviewer = review.reviewer.strip()

    if decision not in {"approved", "rejected"}:
        raise HTTPException(
            status_code=400,
            detail="Decision must be approved or rejected",
        )

    if not reviewer:
        raise HTTPException(
            status_code=400,
            detail="Reviewer is required",
        )

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE approval_requests
            SET status = ?, reviewer = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE request_id = ? AND status = 'pending'
            """,
            (decision, reviewer, request_id),
        )
        connection.commit()

        if cursor.rowcount == 0:
            existing = connection.execute(
                "SELECT status FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()

            if existing is None:
                raise HTTPException(
                    status_code=404,
                    detail="Approval request not found",
                )

            raise HTTPException(
                status_code=409,
                detail=f"Request is already {existing['status']}",
            )

        return {
            "request_id": request_id,
            "status": decision,
            "reviewer": reviewer,
            "message": f"Request {decision}. No action was executed.",
        }

    finally:
        connection.close()
from pathlib import Path
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory=Path(__file__).parent / "frontend", html=True), name="frontend")