import pandas as pd
import re
from sqlalchemy import create_engine

engine = create_engine("sqlite:///warehouse.db")


def clean_and_load():
    print("Starting ETL process...")

    print("Cleaning customers.csv...")
    customers = pd.read_csv('customers.csv')
    customers = customers.dropna(subset=['customer_id'])
    customers['customer_id'] = customers['customer_id'].astype(int)
    customers = customers.drop_duplicates(subset=['customer_id'])
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    customers = customers[customers['email'].str.match(email_regex, na=False)]
    customers['created_at'] = pd.to_datetime(customers['created_at'], errors='coerce')
    customers = customers.dropna(subset=['created_at'])

    print("Cleaning products.csv...")
    products = pd.read_csv('products.csv')
    products = products.dropna(subset=['product_id'])
    products = products.drop_duplicates(subset=['product_id'])
    products = products[products['price'] > 0]

    print("Cleaning orders.csv...")
    orders = pd.read_csv('orders.csv')
    orders = orders.dropna(subset=['order_id', 'customer_id'])
    orders['order_id'] = orders['order_id'].astype(int)
    orders['customer_id'] = orders['customer_id'].astype(int)
    orders = orders.drop_duplicates(subset=['order_id'])
    orders['order_status'] = orders['order_status'].str.lower()
    orders['created_at'] = pd.to_datetime(orders['created_at'], errors='coerce')
    orders = orders.dropna(subset=['created_at'])
    orders = orders[orders['customer_id'].isin(customers['customer_id'])]

    print("Cleaning order_items.csv...")
    items = pd.read_csv('order_items.csv')
    items = items.dropna(subset=['order_item_id', 'order_id', 'product_id'])
    items = items.drop_duplicates(subset=['order_item_id'])
    items = items[items['quantity'] > 0]
    items = items[items['order_id'].isin(orders['order_id'])]
    items = items[items['product_id'].isin(products['product_id'])]

    print("Creating analytical tables...")
    merged_df = items.merge(orders, on='order_id').merge(products, on='product_id')
    merged_df['total_price'] = merged_df['quantity'] * merged_df['price']

    report_customer_spending = merged_df.groupby('customer_id').agg(
        total_spent=('total_price', 'sum'),
        total_orders=('order_id', 'nunique')
    ).reset_index().merge(customers[['customer_id', 'email']], on='customer_id')

    report_product_performance = merged_df.groupby(['product_id', 'name', 'category']).agg(
        total_revenue=('total_price', 'sum'),
        items_sold=('quantity', 'sum')
    ).reset_index()

    print("Loading data into SQLite database...")
    tables = {
        "dim_customers": customers,
        "dim_products": products,
        "fact_orders": orders,
        "fact_order_items": items,
        "report_customer_spending": report_customer_spending,
        "report_product_performance": report_product_performance
    }

    for name, df in tables.items():
        df.to_sql(name, engine, if_exists='replace', index=False)
        print(f"Table '{name}' loaded ({len(df)} rows)")

    print("Success! warehouse.db file created. Task completed!")


if __name__ == "__main__":
    try:
        clean_and_load()
    except Exception as e:
        print(f"An error occurred: {e}")