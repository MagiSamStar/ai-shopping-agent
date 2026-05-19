from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi

from backend.agent.intent import filter_products, tokenize


def build_product_retrieval_text(product: dict[str, Any]) -> str:
    parts = [
        str(product.get("title", "")),
        str(product.get("brand", "")),
        str(product.get("category", "")),
        str(product.get("description", "")),
        str(product.get("sku", "")),
        " ".join(str(tag) for tag in product.get("tags", []) if tag),
    ]
    return " ".join(parts)


def sort_by_rating_and_stock(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        products,
        key=lambda product: (
            -float(product.get("rating", 0) or 0),
            -float(product.get("stock", 0) or 0),
        ),
    )


def rank_products_bm25(
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
        return sort_by_rating_and_stock(filtered)

    tokenized_products = [
        tokenize(build_product_retrieval_text(product))
        for product in filtered
    ]
    if not tokenized_products:
        return []

    bm25 = BM25Okapi(tokenized_products)
    scores = bm25.get_scores(query_tokens)

    scored = [
        (float(score), index, product)
        for index, (score, product) in enumerate(zip(scores, filtered))
    ]
    positive_matches = [item for item in scored if item[0] > 0]
    if not positive_matches:
        return sort_by_rating_and_stock(filtered)

    positive_matches.sort(key=lambda item: (-item[0], item[1]))
    return [product for _, _, product in positive_matches]
