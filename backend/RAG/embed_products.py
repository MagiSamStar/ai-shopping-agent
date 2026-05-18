import json
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT_DIR / "data" / "products.json"
CHROMA_DB_PATH = ROOT_DIR / "chroma_db"
COLLECTION_NAME = "products"
EMBEDDING_MODEL = "text-embedding-3-small"


load_dotenv(BACKEND_DIR / ".env")

#intialzize embedding model
def get_embedding_function():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to embed products.")

    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=EMBEDDING_MODEL,
    )

def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={
            "description": "A collection of products for shopping assistant agent.",
            "hnsw:space": "cosine",
        },
    )

#load product json file
def load_products(path: Path = PRODUCTS_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        products = json.load(file)

    if not isinstance(products, list):
        raise ValueError(f"Expected {path} to contain a list of products.")

    print(f"Loaded {len(products)} products from {path}.")
    return products


def _number_or_default(value: Any, default: int | float) -> int | float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return value
    return default


def create_similarity_search_collection(collection_name: str, collection_metadata: dict = None):
    """Create ChromaDB collection with sentence transformer embeddings"""
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
    try:
        # Try to delete existing collection to start fresh
        client.delete_collection(collection_name)
    except:
        pass
    
    # Create embedding function
    ef=embedding_functions.OpenAIEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    # Create new collection
    return client.create_collection(
        name=collection_name,
        metadata=collection_metadata,
        configuration={
            "hnsw": {"space": "cosine"},
            "embedding_function": ef
        }
    )

def _string_or_default(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value)


def normalize_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_products = []
    used_ids = set()

    for index, product in enumerate(products, start=1):
        raw_id = _string_or_default(product.get("id"), str(index))
        product_id = raw_id
        duplicate_count = 2

        while product_id in used_ids:
            product_id = f"{raw_id}-{duplicate_count}"
            duplicate_count += 1

        used_ids.add(product_id)

        reviews = product.get("reviews", [])
        if not isinstance(reviews, list):
            reviews = []

        normalized = {
            **product,
            "id": product_id,
            "title": _string_or_default(product.get("title"), "Unknown Product"),
            "brand": _string_or_default(product.get("brand"), "Unknown"),
            "category": _string_or_default(product.get("category"), "Unknown"),
            "price": _number_or_default(product.get("price"), 0),
            "rating": _number_or_default(product.get("rating"), 0.0),
            "stock": _number_or_default(product.get("stock"), 0),
            "reviews": reviews,
            "shippingInformation": _string_or_default(
                product.get("shippingInformation"),
                "Unknown",
            ),
            "returnPolicy": _string_or_default(product.get("returnPolicy"), "Unknown"),
            "description": _string_or_default(product.get("description"), ""),
            "thumbnail": _string_or_default(product.get("thumbnail"), ""),
        }
        normalized_products.append(normalized)

    return normalized_products


def build_product_records(
    products: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    documents = []
    ids = []
    metadatas = []

    for product in products:
        review_comments = " ".join(
            review.get("comment", "")
            for review in product["reviews"]
            if isinstance(review, dict)
        ).strip()

        document = "\n".join(
            [
                f"Product: {product['title']}",
                f"Brand: {product['brand']}",
                f"Category: {product['category']}",
                f"Price: ${product['price']}",
                f"Rating: {product['rating']}",
                f"Available: {'Yes' if product['stock'] > 0 else 'No'}",
                f"Reviews: {review_comments}",
                f"Stock: {product['stock']}",
                f"Shipping: {product['shippingInformation']}",
                f"Return Policy: {product['returnPolicy']}",
                f"Description: {product['description']}",
                f"Thumbnail: {product['thumbnail']}",
            ]
        )

        documents.append(document)
        ids.append(product["id"])
        metadatas.append(
            {
                "title": product["title"],
                "brand": product["brand"],
                "sku": product.get("sku", ""),
                "category": product["category"],
                "price": product["price"],
                "rating": product["rating"],
                "stock": product["stock"],
                "shipping": product["shippingInformation"],
                "return_policy": product["returnPolicy"],
                "description": product["description"],
                "thumbnail": product["thumbnail"],
            }
        )

    return documents, ids, metadatas
def build_where_filter(
        brand: str | None = None,
        category: str | None = None,
        price_range: tuple[float, float] | None = None,
        rating_threshold: float | None = None,
        in_stock_only: bool = False,
        sku: str | None = None
):
    filters = []
    if brand:
        filters.append({"brand": brand})
    if category:
        filters.append({"category": category})
    if price_range:
        filters.append({"price": {"$gte": price_range[0], "$lte": price_range[1]}})
    if rating_threshold:
        filters.append({"rating": {"$gte": rating_threshold}})
    if in_stock_only:
        filters.append({"stock": {"$gt": 0}})
    if sku:
        filters.append({"sku": sku})

    if len(filters) == 1:
        return filters[0]
    elif len(filters) > 1:
        return {"$and": filters}

    return None

def populate_collection(collection, products: list[dict[str, Any]]) -> None:
    normalized_products = normalize_products(products)
    documents, ids, metadatas = build_product_records(normalized_products)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"Upserted {len(ids)} products into '{COLLECTION_NAME}'.")


def main():
    collection = get_collection()
    print(f"Collection '{COLLECTION_NAME}' ready.")

    products = load_products()
    populate_collection(collection, products)


if __name__ == "__main__":
    main()
