from backend.RAG.embed_products import load_products, normalize_products, get_collection

def main():
    products = normalize_products(load_products())
    collection = get_collection()

    json_categories = sorted(set(p["category"] for p in products))

    all_items = collection.get()
    db_categories = sorted(set(
        metadata["category"]
        for metadata in all_items["metadatas"]
    ))

    print("\nJSON categories:")
    print(json_categories)

    print("\nChromaDB categories:")
    print(db_categories)

    print("\nFurniture in JSON:")
    furniture_json = [p for p in products if p["category"] == "furniture"]
    print(len(furniture_json))

    print("\nFurniture in ChromaDB:")
    furniture_db = collection.get(where={"category": "furniture"})
    print(len(furniture_db["ids"]))
    print(furniture_db["ids"][:5])

if __name__ == "__main__":
    main()