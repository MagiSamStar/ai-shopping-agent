import json
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.RAG.embed_products import (
    build_product_records,
    build_where_filter,
    get_collection,
    normalize_products,
)
from backend.agent.intent import (
    is_greeting,
    is_list_query,
    is_product_related_query,
    is_review_query,
    parse_in_stock_only,
    parse_price_max,
    rank_products,
)
from backend.agent.responses import (
    build_chat_response,
    build_follow_up_question,
    build_greeting_response,
    build_list_answer,
    build_off_topic_response,
    build_review_answer,
    build_single_answer,
    serialize_product,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT_DIR / "data" / "products.json"
UPLOADS_DIR = ROOT_DIR / "backend" / "uploads"

app = FastAPI(title="Shopping Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


def read_products() -> list[dict[str, Any]]:
    if not PRODUCTS_PATH.exists():
        return []

    with PRODUCTS_PATH.open("r", encoding="utf-8") as file:
        products = json.load(file)

    if not isinstance(products, list):
        raise HTTPException(status_code=500, detail="products.json must contain a list.")

    return products


def write_products(products: list[dict[str, Any]]) -> None:
    with PRODUCTS_PATH.open("w", encoding="utf-8") as file:
        json.dump(products, file, indent=2)


def get_next_product_id(products: list[dict[str, Any]]) -> int:
    numeric_ids = []
    for product in products:
        try:
            numeric_ids.append(int(product.get("id")))
        except (TypeError, ValueError):
            continue

    return (max(numeric_ids) + 1) if numeric_ids else 1


def save_upload(image: UploadFile | None) -> str:
    if image is None:
        return ""

    suffix = Path(image.filename or "").suffix or ".bin"
    filename = f"{uuid.uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / filename

    with destination.open("wb") as buffer:
        buffer.write(image.file.read())

    return f"/uploads/{filename}"


def upsert_product_into_collection(product: dict[str, Any]) -> None:
    collection = get_collection()
    normalized_product = normalize_products([product])[0]
    documents, ids, metadatas = build_product_records([normalized_product])

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


class ChatRequest(BaseModel):
    message: str
    sku: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    price_max: Optional[float] = None
    in_stock_only: bool = False


@app.post("/chat")
def post_chat(payload: ChatRequest):
    query_text = payload.message.strip()
    products = read_products()

    if is_greeting(query_text):
        return build_greeting_response()

    if not is_product_related_query(query_text, products):
        return build_off_topic_response()

    effective_price_max = payload.price_max if payload.price_max is not None else parse_price_max(query_text)
    effective_in_stock_only = payload.in_stock_only or parse_in_stock_only(query_text)
    filters = {
        "sku": payload.sku,
        "category": payload.category,
        "brand": payload.brand,
        "price_max": effective_price_max,
        "in_stock_only": effective_in_stock_only,
    }

    if payload.sku:
        collection = get_collection()
        where_filter = build_where_filter(sku=payload.sku)
        results = collection.get(where=where_filter, include=["metadatas"])
        metadatas = results.get("metadatas", [])
        exact_match = metadatas[0] if metadatas else None

        if not exact_match:
            return build_chat_response(
                f"I could not find a product with SKU {payload.sku}.",
                [],
                exact_match=None,
                tool_used="chroma_get",
                query=query_text,
                filters=filters,
                follow_up_question="Try another SKU or ask me for a product by name.",
            )

        match = serialize_product(exact_match)
        return build_chat_response(
            build_single_answer(match),
            [match],
            exact_match=match,
            tool_used="chroma_get",
            query=query_text,
            filters=filters,
            follow_up_question=build_follow_up_question(match),
            intent="single",
            response_type="single",
        )

    ranked_products = rank_products(
        products,
        query_text,
        brand=payload.brand,
        category=payload.category,
        price_max=effective_price_max,
        in_stock_only=effective_in_stock_only,
    )

    if is_list_query(query_text):
        matches = [serialize_product(product) for product in ranked_products[:5]]
        if matches:
            answer = build_list_answer(matches)
            follow_up_question = "Which one are you interested in knowing more about?"
        else:
            answer = "I could not find any matching products in stock right now."
            follow_up_question = "Try a different product name, brand, or category."

        return build_chat_response(
            answer,
            matches,
            exact_match=None,
            tool_used="catalog_search",
            query=query_text,
            filters=filters,
            follow_up_question=follow_up_question,
            intent="list",
            response_type="list",
        )

    if not ranked_products and effective_price_max is not None:
        ranked_products = rank_products(
            products,
            query_text,
            brand=payload.brand,
            category=payload.category,
            in_stock_only=effective_in_stock_only,
        )

    matches = [serialize_product(ranked_products[0])] if ranked_products else []

    if matches:
        if is_review_query(query_text):
            answer = build_review_answer(matches[0])
        else:
            answer = build_single_answer(matches[0])
        follow_up_question = build_follow_up_question(matches[0])
    else:
        answer = "I could not find any products that match your request."
        follow_up_question = "Try rephrasing your request or ask for a category like eyeshadow, mascara, or fragrance."

    return build_chat_response(
        answer,
        matches,
        exact_match=None,
        tool_used="catalog_search" if matches else "catalog_fallback",
        query=query_text,
        filters=filters,
        follow_up_question=follow_up_question,
        intent="single" if matches else "none",
        response_type="single" if matches else "none",
    )


@app.get("/")
def read_root():
    return {"message": "Shopping Agent API is running!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/products")
def list_products():
    return read_products()


@app.post("/products/upload")
async def upload_products(file: UploadFile):
    contents = await file.read()
    try:
        uploaded = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Upload file must contain valid JSON.") from exc

    if isinstance(uploaded, dict):
        uploaded = [uploaded]

    if not isinstance(uploaded, list):
        raise HTTPException(status_code=400, detail="Upload file must contain a JSON object or list of objects.")

    products = read_products()
    added = 0

    for item in uploaded:
        if not isinstance(item, dict):
            continue
        if not item.get("id"):
            item["id"] = get_next_product_id(products)
        products.append(item)
        upsert_product_into_collection(item)
        added += 1

    write_products(products)

    return {
        "message": "Products uploaded successfully.",
        "added": added,
    }


@app.post("/products")
async def create_product(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    brand: str = Form(...),
    sku: str = Form(...),
    stock: int = Form(0),
    rating: float = Form(0.0),
    shipping_information: str = Form("Unknown"),
    return_policy: str = Form("Unknown"),
    thumbnail_url: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    products = read_products()
    product_id = get_next_product_id(products)

    thumbnail = thumbnail_url or save_upload(image)

    product = {
        "id": product_id,
        "title": title,
        "description": description,
        "category": category,
        "price": price,
        "brand": brand,
        "sku": sku,
        "stock": stock,
        "rating": rating,
        "shippingInformation": shipping_information,
        "returnPolicy": return_policy,
        "thumbnail": thumbnail,
        "images": [thumbnail] if thumbnail else [],
        "reviews": [],
    }

    products.append(product)
    write_products(products)
    upsert_product_into_collection(product)

    return {
        "message": "Product created successfully.",
        "product": product,
    }
