from __future__ import annotations

import re
from typing import Any

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

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|hiya|good morning|good afternoon|good evening)[!.?\s]*$",
    re.IGNORECASE,
)
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
REVIEW_INTENT_PATTERNS = (
    re.compile(r"\breviews?\b", re.IGNORECASE),
    re.compile(r"\bcustomer reviews?\b", re.IGNORECASE),
    re.compile(r"\bwhat do (?:the )?reviews say\b", re.IGNORECASE),
    re.compile(r"\bwhat are the reviews\b", re.IGNORECASE),
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
    "review",
    "reviews",
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]+", " ", value.lower()).strip()


def tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", normalize_text(value)) if token and token not in STOPWORDS]


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


def parse_result_limit(message: str, default: int = 5, maximum: int = 10) -> int:
    match = re.search(
        r"\b(?:show|list|find|get|recommend)?\s*(\d{1,2})\s+(?:of\s+)?(?:these|this|those|items?|products?)?\b",
        message,
        flags=re.IGNORECASE,
    )
    if not match:
        return default

    requested = int(match.group(1))
    return max(1, min(requested, maximum))


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
    if any(pattern.search(message) for pattern in REVIEW_INTENT_PATTERNS):
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


def is_review_query(message: str) -> bool:
    return any(pattern.search(message) for pattern in REVIEW_INTENT_PATTERNS)


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
