# BM25 Retrieval Code Changes

This note explains the changes made to add BM25 product retrieval and fix list responses such as:

```text
show me 3 products
show me 3 of this item
show me 4 fragrances
```

## Problem

The assistant had two issues:

1. The backend always returned up to 5 list results because `backend/app.py` used:

```python
ranked_products[:5]
```

2. The frontend displayed only one product for list responses because it converted the first match into a single `product` card:

```ts
product: data.product ?? data.matches?.[0]
```

That meant a list query could say it found several items, but the UI would only show the first one.

## Files Changed

### `backend/agent/retrieval.py`

This new file contains the BM25 product ranking logic.

Main function:

```python
rank_products_bm25(...)
```

What it does:

- filters products by brand, category, price, and stock
- builds searchable text from product fields
- tokenizes the query and product text
- scores products with `BM25Okapi`
- returns matching products ordered by BM25 score
- falls back to rating and stock if the query has no useful text match

Important fields used for retrieval:

```python
title
brand
category
description
sku
tags
```

### `backend/app.py`

The chat route now imports BM25 retrieval:

```python
from backend.agent.retrieval import rank_products_bm25
```

The old manual ranking calls were replaced:

```python
rank_products_bm25(...)
```

The list response now respects the requested number of results:

```python
matches = [serialize_product(product) for product in ranked_products[:result_limit]]
```

Before, it was hardcoded to:

```python
ranked_products[:5]
```

### `backend/agent/intent.py`

This file now includes:

```python
parse_result_limit(message: str, default: int = 5, maximum: int = 10) -> int
```

Purpose:

- detects numbers in list-style requests
- returns that number as the result limit
- defaults to 5 if no number is found
- caps the limit at 10 so the assistant does not return too many products

Example behavior:

```text
show me 3 products -> 3
show me products -> 5
show me 20 products -> 10
```

### `frontend/my-app/src/App.tsx`

The frontend no longer turns the first list match into a single product card.

Before:

```ts
product: data.product ?? data.matches?.[0]
```

After:

```ts
product: data.product
```

Why this matters:

- single-product responses still render the large product card
- list responses now render all returned matches in the recommendation list

### `backend/requirements.txt`

Added:

```text
rank-bm25==0.2.2
```

Install it with:

```powershell
.\.venv\Scripts\pip.exe install rank-bm25==0.2.2
```

## How The Flow Works Now

1. User sends a chat message from the frontend.
2. Frontend posts to:

```text
POST /chat
```

3. Backend reads the message.
4. Backend checks whether it is a greeting, off-topic, SKU lookup, list query, review query, or single-product query.
5. For normal product search, backend calls:

```python
rank_products_bm25(...)
```

6. If the query is a list query, backend reads the requested count:

```python
result_limit = parse_result_limit(query_text)
```

7. Backend returns that many matches:

```python
ranked_products[:result_limit]
```

8. Frontend renders:

- `data.product` as one large card for single-product responses
- `data.matches` as multiple smaller cards for list responses

## How To Fix This Yourself Next Time

If the assistant says it found several products but only one appears:

1. Check the backend response in the browser network tab.
2. Look at `matches`, `match_count`, and `response_type`.
3. If `matches` has multiple products but the UI shows one, the bug is in frontend rendering.
4. If `matches` only has one product, the bug is in backend ranking or slicing.
5. Search for hardcoded slices like:

```python
[:5]
[:1]
```

6. Search frontend code for fallback logic like:

```ts
data.matches?.[0]
```

That kind of fallback is useful for single-result responses, but it can accidentally collapse list responses into one item.

## Quick Tests

Run the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --port 8010
```

Run a direct API test:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8010/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"show me 3 products"}'
```

Expected:

```text
match_count: 3
response_type: list
```

Build the frontend:

```powershell
cd frontend/my-app
npm run build
```
