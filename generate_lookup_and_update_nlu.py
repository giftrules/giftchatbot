# generate_lookup_and_update_nlu.py

from mywebapp import create_app,db
from mywebapp.models import Product, Category
import os

# Initialize Flask app context
app = create_app()
app.app_context().push()

# File paths
lookup_file_path = "data/product_lookup.yml"

# Step 1: Fetch product names
product_names = set(
    p.name.strip().lower()
    for p in Product.query.all()
    if p.name and p.name.strip()
)

# Step 2: Fetch category names
category_names = set(
    c.name.strip().lower()
    for c in Category.query.all()
    if c.name and c.name.strip()
)

# Combine and sort all terms for the lookup list
lookup_terms = sorted(product_names.union(category_names))

# Step 3: Write to lookup file
os.makedirs(os.path.dirname(lookup_file_path), exist_ok=True)

with open(lookup_file_path, "w", encoding="utf-8") as f:
    f.write("- lookup: product_name\n")
    f.write("  examples: |\n")
    for term in lookup_terms:
        f.write(f"    - {term}\n")

print(f"✅ Lookup file updated with {len(lookup_terms)} entries (products + categories).")