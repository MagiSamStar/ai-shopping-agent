import json
import re
import uuid
from pydantic import BaseModel
from pathlib import Path
from typing import Any
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.RAG.embed_products import (
    build_product_records,
    build_where_filter,
    get_collection,
    normalize_products,
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

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "can",
    "do",
    "for",
    "get",
    "give",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "show",
    "the",
    "to",
    "what",
    "which",
    "with",
    "you",
    "your",
}

GREETING_PATTERN = re.compile(r"^\s*(hi|hello|hey|hiya|good morning|good afternoon|good evening)[!.?\s]*$", re.IGNORECASE)
LIST_INTENT_PATTERNS = (
    re.compile(r"\bhow many\b", re.IGNORECASE),
    re.compile(r"\bshow me\b", re.IGNORECASE),
    re.compile(r"\blist\b", re.IGNORECASE),
    re.compile(r"\bdo you have\b", re.IGNORECASE),
    re.compile(r"\bin stock\b", re.IGNORECASE),
    re.compile(r"\bavailable\b", re.IGNORECASE),
    re.compile(r"\bwhat .*have\b", re.IGNORECASE),
)
SPECIFIC_INTENT_PATTERNS = (
    re.compile(r"\btell me about\b", re.IGNORECASE),
    re.compile(r"\bmore info\b", re.IGNORECASE),
    re.compile(r"\bdetails?\b", re.IGNORECASE),
    re.compile(r"\bdescribe\b", re.IGNORECASE),
)

SHOPPING_TERMS = {
    "product",
    "products",
    "item",
    "items",
    "search",
    "find",
    "show",
    "list",
    "recommend",
    "recommendation",
    "stock",
    "available",
    "availability",
    "price",
    "priced",
    "cost",
    "brand",
    "category",
    "sku",
    "buy",
    "purchase",
    "compare",
    "details",
    "detail",
    "info",
}


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


def parse_price_max(message: str) -> float | None:
    match = re.search(
        r"(?:under|below|less than|up to|at most|max(?:imum)?(?: of)?)\s*\$?\s*(\d+(?:\.\d+)?)",
        message,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return float(match.group(1))


def parse_in_stock_only(message: str) -> bool:
    lowered = message.lower()
    return "in stock" in lowered or "available now" in lowered


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]+", " ", value.lower()).strip()


def tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", normalize_text(value)) if token and token not in STOPWORDS]


def build_catalog_terms(products: list[dict[str, Any]]) -> set[str]:
    terms: set[str] = set()
    for product in products:
        terms.update(tokenize(str(product.get("title", ""))))
        terms.update(tokenize(str(product.get("brand", ""))))
        terms.update(tokenize(str(product.get("category", ""))))
        terms.update(tokenize(str(product.get("description", ""))))
        for tag in product.get("tags", []) or []:
            terms.update(tokenize(str(tag)))
    return terms


def is_product_related_query(message: str, products: list[dict[str, Any]]) -> bool:
    lowered = message.lower().strip()
    tokens = tokenize(lowered)
    if not tokens:
        return False

    if any(pattern.search(message) for pattern in LIST_INTENT_PATTERNS):
        return True
    if any(pattern.search(message) for pattern in SPECIFIC_INTENT_PATTERNS):
        return True

    if any(token in SHOPPING_TERMS for token in tokens):
        return True

    catalog_terms = build_catalog_terms(products)
    return any(token in catalog_terms for token in tokens)


def is_greeting(message: str) -> bool:
    return bool(GREETING_PATTERN.match(message))


def is_list_query(message: str) -> bool:
    if any(pattern.search(message) for pattern in SPECIFIC_INTENT_PATTERNS):
        return False
    return any(pattern.search(message) for pattern in LIST_INTENT_PATTERNS)


def is_specific_query(message: str) -> bool:
    return any(pattern.search(message) for pattern in SPECIFIC_INTENT_PATTERNS)


def build_product_search_text(product: dict[str, Any]) -> str:
    parts = [
        str(product.get("title", "")),
        str(product.get("brand", "")),
        str(product.get("category", "")),
        str(product.get("description", "")),
        " ".join(str(tag) for tag in product.get("tags", []) if tag),
    ]
    return normalize_text(" ".join(parts))


def score_product(product: dict[str, Any], query_tokens: list[str]) -> int:
    search_text = build_product_search_text(product)
    title_text = normalize_text(str(product.get("title", "")))
    brand_text = normalize_text(str(product.get("brand", "")))
    category_text = normalize_text(str(product.get("category", "")))
    tags_text = normalize_text(" ".join(str(tag) for tag in product.get("tags", []) if tag))

    score = 0
    for token in query_tokens:
        if token in title_text:
            score += 6
        if token in tags_text:
            score += 5
        if token in category_text:
            score += 4
        if token in brand_text:
            score += 3
        if token in search_text:
            score += 2

    if "eyeshadow" in query_tokens and "eyeshadow" in search_text:
        score += 10
    if "eye" in query_tokens and "shadow" in query_tokens and "eyeshadow" in search_text:
        score += 10

    if any(token in search_text for token in query_tokens):
        score += 1

    return score


def filter_products(
    products: list[dict[str, Any]],
    *,
    brand: str | None = None,
    category: str | None = None,
    price_max: float | None = None,
    in_stock_only: bool = False,
) -> list[dict[str, Any]]:
    filtered = []
    for product in products:
        if brand and product.get("brand") != brand:
            continue
        if category and product.get("category") != category:
            continue
        if price_max is not None and product.get("price", 0) > price_max:
            continue
        if in_stock_only and product.get("stock", 0) <= 0:
            continue
        filtered.append(product)
    return filtered


def rank_products(
    products: list[dict[str, Any]],
    query: str,
    *,
    brand: str | None = None,
    category: str | None = None,
    price_max: float | None = None,
    in_stock_only: bool = False,
) -> list[dict[str, Any]]:
    filtered = filter_products(
        products,
        brand=brand,
        category=category,
        price_max=price_max,
        in_stock_only=in_stock_only,
    )

    query_tokens = tokenize(query)
    if not query_tokens:
        return sorted(
            filtered,
            key=lambda product: (-float(product.get("rating", 0) or 0), -float(product.get("stock", 0) or 0)),
        )

    scored = [
        (score_product(product, query_tokens), index, product)
        for index, product in enumerate(filtered)
    ]

    scored.sort(key=lambda item: (-item[0], item[1]))
    ranked = [product for score, _, product in scored if score > 0]
    if ranked:
        return ranked

    return sorted(
        filtered,
        key=lambda product: (-float(product.get("rating", 0) or 0), -float(product.get("stock", 0) or 0)),
    )


def build_greeting_response() -> dict[str, Any]:
    return build_chat_response(
        "Hello, how can I help you today?",
        [],
        exact_match=None,
        tool_used="greeting",
        query="",
        filters={},
        follow_up_question=None,
        intent="greeting",
        response_type="greeting",
    )


def build_off_topic_response() -> dict[str, Any]:
    return build_chat_response(
        "I don't have that information. I can only help with product searches and product details.",
        [],
        exact_match=None,
        tool_used="topic_guard",
        query="",
        filters={},
        follow_up_question="Ask me about a product, brand, category, price, stock, or SKU.",
        intent="off_topic",
        response_type="off_topic",
    )


def build_list_answer(matches: list[dict[str, Any]]) -> str:
    count = len(matches)
    if count == 1:
        return "We have 1 matching item in stock at the moment."
    return f"We have {count} matching items in stock at the moment."


def build_single_answer(product: dict[str, Any]) -> str:
    title = product.get("title", "This product")
    brand = product.get("brand", "Unknown brand")
    price = product.get("price", 0)
    rating = product.get("rating", 0)
    stock = int(product.get("stock", 0) or 0)
    status = product.get("availabilityStatus") or ("In Stock" if stock > 0 else "Out of Stock")
    description = product.get("description", "").strip()

    summary = f"I found {title} by {brand} for ${price:.2f}. It is rated {rating:.1f}/5 and is currently {status.lower()}."
    if description:
        summary += f" {description}"
    return summary


def serialize_product(product: dict[str, Any]) -> dict[str, Any]:
    stock = int(product.get("stock", 0) or 0)
    thumbnail = product.get("thumbnail") or ""

    return {
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "sku": product.get("sku", ""),
        "category": product.get("category", ""),
        "price": product.get("price", 0),
        "rating": product.get("rating", 0),
        "stock": stock,
        "thumbnail": thumbnail,
        "availabilityStatus": product.get(
            "availabilityStatus",
            "In Stock" if stock > 0 else "Out of Stock",
        ),
        "description": product.get("description", ""),
        "shippingInformation": product.get("shippingInformation", ""),
        "returnPolicy": product.get("returnPolicy", ""),
        "tags": product.get("tags", []),
    }


def build_follow_up_question(product: dict[str, Any]) -> str:
    category = str(product.get("category", "")).lower()
    title = product.get("title", "this item")

    if category == "beauty":
        return f"Would you like more info on {title}, like ingredients, reviews, or similar shades?"
    if category == "fragrances":
        return f"Would you like more info on {title}, like scent notes, longevity, or bottle size?"
    if category == "groceries":
        return f"Would you like more info on {title}, like ingredients, nutrition, or similar products?"

    return f"Would you like more info on {title}, or should I find similar products?"


def build_product_answer(product: dict[str, Any]) -> str:
    title = product.get("title", "This product")
    brand = product.get("brand", "Unknown brand")
    price = product.get("price", 0)
    rating = product.get("rating", 0)
    stock = int(product.get("stock", 0) or 0)
    status = product.get("availabilityStatus") or ("In Stock" if stock > 0 else "Out of Stock")
    description = product.get("description", "").strip()

    summary = f"I found {title} by {brand} for ${price:.2f}. It is rated {rating:.1f}/5 and is currently {status.lower()}."
    if description:
        summary += f" {description}"
    return summary


def build_chat_response(
    answer: str,
    matches: list[dict[str, Any]],
    *,
    exact_match: dict[str, Any] | None = None,
    tool_used: str | None = None,
    query: str | None = None,
    filters: dict[str, Any] | None = None,
    follow_up_question: str | None = None,
    intent: str | None = None,
    response_type: str | None = None,
) -> dict[str, Any]:
    response_product = matches[0] if matches and response_type == "single" else None
    return {
        "answer": answer,
        "matches": matches,
        "recommendations": matches,
        "match_count": len(matches),
        "exact_match": exact_match,
        "tool_used": tool_used,
        "query": query,
        "filters": filters,
        "follow_up_question": follow_up_question,
        "product": response_product,
        "intent": intent,
        "response_type": response_type,
    }


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
async def upload_products(file:UploadFile):
    contents = await file.read()
    products = json.loads(contents)

    results = upsert_product_into_collection(products)
    return results 

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
