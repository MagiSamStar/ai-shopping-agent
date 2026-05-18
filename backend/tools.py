import requests
from langchain_core.tools import tool





@tool
def compare_prices(product_a: str, product_b: str):
    """
    Compares prices of products across different retailers."""
    return {
        "product_a": {
            "name": product_a,
            "Retailer A": 10,
            "Retailer B": 12,
        },
        "product_b": {
            "name": product_b,
            "Retailer A": 20,
            "Retailer B": 18,
        }
    }

cart = []

@tool 
def add_to_cart(product: str, retailer:str,price:float):
    """
    Adds a product to the user's shopping cart on the specified retailer's website."""
    item = {
        "product": product,
        "retailer": retailer,
        "price": price
    }

    cart.append(item)

    return {
        "status": "success",
        "cart_total": sum(i["price"] for i in cart),
        "items_in_cart": len(cart),
        "added_item": item
    }

@tool
def calculate_total(cart):
    """
    Calculates the total price of items in the user's shopping cart."""

    total = sum(item['price'] for item in cart)
    return {
        "cart_total": total,
        "item_count": len(cart)
    }

tools = [
    compare_prices,
    add_to_cart,
    calculate_total
]

tools_by_name={tool.name: tool for tool in tools}