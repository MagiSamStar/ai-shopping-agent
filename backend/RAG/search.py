from embed_products import *

search_history = []
PRODUCTS_PATH = ROOT_DIR / "data" / "products.json"
SEARCH_COLLECTION_NAME = "interactive_product_search"


def main():
    """Main function for interactive CLI product search and recommendation system."""
    print("🛍️  Interactive Product Search and Recommendation System")
    print("=" * 50)
    print("Loading product database...")

    products = load_products(path=PRODUCTS_PATH)
    print(f"✅ Loaded {len(products)} products successfully")

    # Create and populate search collection
    collection = create_similarity_search_collection(
        SEARCH_COLLECTION_NAME,
        {"description": "A collection for interactive product search and recommendation"},
    )

    populate_collection(collection, products)

    # Start interactive chatbot
    interactive_product_chatbot(collection)

def search_products(
    collection,
    query: str,
    brand: str | None = None,
    category: str | None = None,
    sku: str | None = None,
    n_results: int = 5,
):
    where_filter = build_where_filter(
        brand=brand,
        category=category,
        sku=sku,
    )

    kwargs = {
        "query_texts": [query],
        "n_results": n_results,
    }

    if where_filter:
        kwargs["where"] = where_filter

    return collection.query(**kwargs)


def parse_sku_search(user_input: str) -> str | None:
    if not user_input.lower().startswith("sku:"):
        return None

    sku = user_input[4:].strip()
    return sku or None


def print_search_results(results: dict, exact_match: bool = False) -> None:
    matches = results.get("metadatas", [[]])[0]

    if not matches:
        print("   No products found matching your search.")
        print("   Try refining your search or check for typos.")
        return

    if exact_match:
        product = matches[0]
        print("   Found 1 product matching your SKU:")
        print("-" * 50)
        print(
            f"   {product['title']} - {product['category']} - "
            f"${product['price']} - Rating: {product['rating']}"
        )
        return

    print(f"   Found {len(matches)} products matching your search:")
    print("-" * 50)
    for i, product in enumerate(matches, start=1):
        print(
            f"\n{i}. {product['title']} - {product['category']} - "
            f"${product['price']} - Rating: {product['rating']}"
        )

def looks_like_sku(user_input: str) -> str:
    text = user_input.strip()
    return "-" in text and len(text) >=8

def interactive_product_chatbot(collection):
    """Interactive CLI chatbot for product search and recommendation."""
    print("\n" + "=" * 50)
    print("🤖 INTERACTIVE PRODUCT SEARCH CHATBOT")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n🔍 Search for Product or SKU Number: ").strip()

            if not user_input:
                print("   Please enter a Product name, Category or Sku")
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Thank you for using the Product Recommendation System!")
                print("   Goodbye!")
                break

            sku = parse_sku_search(user_input)
            if user_input.lower().startswith("sku:") and not sku:
                print("   Please provide a SKU after 'sku:'.")
                continue

            if sku or looks_like_sku(user_input):
                exact_sku = sku or user_input.strip()
                results = search_products(collection, query=exact_sku, n_results=1)
                print_search_results(results, exact_match=True)
            else:
                results = search_products(collection, query=user_input, n_results=5)
                print_search_results(results)
            
            search_history.append(user_input)
        except KeyboardInterrupt:
            print("\n\n👋 System interrupted. Goodbye!")
            break
        except Exception as error:
            print(f"❌ Error processing search: {error}")


if __name__ == "__main__":
    main()
