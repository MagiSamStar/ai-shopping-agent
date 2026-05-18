from __future__ import annotations

from typing import Any


def serialize_product(product: dict[str, Any]) -> dict[str, Any]:
    stock = int(product.get("stock", 0) or 0)
    thumbnail = product.get("thumbnail") or ""
    reviews = product.get("reviews", [])
    if not isinstance(reviews, list):
        reviews = []

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
        "reviews": reviews,
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


def build_list_answer(matches: list[dict[str, Any]]) -> str:
    count = len(matches)
    if count == 1:
        return "We have 1 matching item in stock at the moment."
    return f"We have {count} matching items in stock at the moment."


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


def build_review_answer(product: dict[str, Any]) -> str:
    reviews = product.get("reviews", []) or []
    title = product.get("title", "This product")

    if not reviews:
        return f"I found {title}, but I do not have customer reviews for it in the catalog right now."

    review_lines = []
    for review in reviews[:3]:
        if not isinstance(review, dict):
            continue
        reviewer = review.get("reviewerName", "A customer")
        rating = review.get("rating", product.get("rating", 0))
        comment = str(review.get("comment", "")).strip()
        if comment:
            review_lines.append(f"{reviewer} rated it {rating}/5 and said: {comment}")
        else:
            review_lines.append(f"{reviewer} rated it {rating}/5.")

    intro = f"Here are a few customer reviews for {title}:"
    if review_lines:
        return " ".join([intro, " ".join(review_lines)])
    return f"I found {title}, but there are no readable review comments available right now."
