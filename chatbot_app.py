from flask import Flask, render_template, request, jsonify, flash
import requests
from mywebapp import create_app
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from  mywebapp.models import *
from flask import send_from_directory
from sqlalchemy import func
API_URL = 'http://localhost:5005/webhooks/rest/webhook'

#API_URL='http://localhost:5055/webhook'

app = create_app()
#@app.route('/')
#def index():
 #  return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    user_message = request.json['message']
    print("User Message:", user_message)
    # Send user message to Rasa and get bot's response
    rasa_response = requests.post(API_URL, json={ 'message': user_message})
    rasa_response_json = rasa_response.json()
    print("Rasa Response:", rasa_response_json)
    bot_response = rasa_response_json[0]['text'] if rasa_response_json else 'Sorry, I didn\'t understand that. May you please rephrase.'
    return jsonify({'response': bot_response})
# Initialize the database (this will create the tables in the database)
@app.route("/thechat", methods=["GET", "POST"])
def chat():
    user_message = request.form["msg"]
    user_id = request.form["customer_id"]
    usertype = request.form["usertype"]
    print("User Message:", user_message,"User ID:", user_id,"User Type:", usertype)
    # Send user message to Rasa and get bot's response
    # Detect command to trigger action_check_stock
    rasa_response = requests.post(API_URL, json={'message': user_message, "metadata": {'customer_id': user_id,'usertype': usertype}})
    rasa_response_json = rasa_response.json()
    print("Rasa Response:", rasa_response_json)
    #bot_response = rasa_response_json[0]['text'] if rasa_response_json else 'Sorry, I didn\'t understand that.'
    bot_response = " | ".join([res["text"] for res in rasa_response_json if
                              "text" in res]) if rasa_response_json else "Sorry, I didn't understand that."
    return bot_response
# Models here (reusing your provided definitions)
# Assuming the models ChatbotReview, Product, Order, OrderItem, Cart, CartItem are already defined
# Include them here if needed

# ---------------------- Product Endpoints ----------------------
@app.route('/products', methods=['GET'])
def get_products():
    name = request.args.get('name')
    print("Product Name or Category:", name)
    my_list = ["everything", "anything", "all"]

    if name and name.lower() not in my_list:
        # Search for products by name OR by category name
        products = Product.query.join(Category).filter(
            db.or_(
                Product.name.ilike(f"%{name}%"),
                Category.name.ilike(f"%{name}%")
            )
        ).all()
    else:
        products = Product.query.all()

    if products:
        print("Matched Products:")
        for p in products:
            print(f"- ID: {p.product_id}, Name: {p.name}, Category: {p.category.name}, Price: {p.price}, Stock: {p.stock_quantity}")
    else:
        print("No products found.")

    return jsonify([{
        'id': p.product_id,
        'name': p.name,
        'price': p.price,
        'stock': p.stock_quantity,
        'category': p.category.name  # Include category name in the response
    } for p in products])
# ---------------------- CartItem Endpoints ----------------------
@app.route('/cart_items', methods=['POST'])
def add_cart_item():
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        product_name = data.get('product_name')
        quantity = int(data.get('quantity', 1))

        print("Product Name:", product_name)
        print("Customer ID:", customer_id)
        print("Quantity:", quantity)

        my_list = ["everything", "anything", "all","electronics"]
        if product_name in my_list:
            product =  Product.query.all()
        else :
            product = Product.query.filter(Product.name.ilike(f"%{product_name}%")).first()
        if not product or product.stock_quantity < quantity:
            print("Product not found.")
            return jsonify({'message': 'Product not available or insufficient stock'}), 400

        cart = Cart.query.filter_by(customer_id=customer_id).first()
        if not cart:
            cart = Cart(customer_id=customer_id)
            db.session.add(cart)
            db.session.commit()
        print("passed")
        cart_item = CartItem(cart_id=cart.cart_id, product_id=product.product_id, quantity=quantity)
        db.session.add(cart_item)
        db.session.commit()

        return jsonify({'message': f"{quantity} {product_name} added to cart"}), 201

    except Exception as e:
        print(f"Error adding cart item: {e}")
        return jsonify({'message': 'Internal server error'}), 500



@app.route('/download/manual')
def download_manual():
    return send_from_directory('documents', 'Chatbot_User_Manual.docx', as_attachment=True)

# ---------------------- Review Endpoint ----------------------
@app.route('/chatbotreviews', methods=['POST'])
def submit_review():
    data = request.get_json()
    customer_id = data['customer_id']
    comment = data['comment']
    print("User Comment:", comment)
    print("Customer ID:", customer_id)
    if not customer_id or not comment:
        return jsonify({'message': 'Missing fields'}), 400

    review = ChatbotReview(customer_id=customer_id, comment=comment)
    db.session.add(review)
    db.session.commit()
    return jsonify({'message': 'Review submitted successfully'}), 201


# ---------------------- Total Cart Price Endpoint ----------------------
@app.route('/cart/total/<int:customer_id>', methods=['GET'])
def get_cart_total(customer_id):
    cart = Cart.query.filter_by(customer_id=customer_id).first()
    if not cart:
        return jsonify({'total': 0})

    total = 0
    for item in cart.cart_items:
        total += item.quantity * item.product.price
    return jsonify({'total': total})


# Get all cart items for a customer
@app.route("/cart_items/<int:customer_id>", methods=["GET"])
def get_cart_items(customer_id):
    items = CartItem.query.join(CartItem.cart).filter_by(customer_id=customer_id).all()
    if not items:
        return jsonify([]), 200

    result = []
    for item in items:
        product = item.product
        result.append({
            "cart_item_id": item.cart_item_id,
            "product_id": product.product_id,
            "product_name": product.name,
            "quantity": item.quantity,
            "unit_price": product.price
        })
    return jsonify(result), 200

# Clear cart items for a customer (optional, used after order creation)
@app.route("/cart_items/clear/<int:customer_id>", methods=["DELETE"])
def clear_cart(customer_id):
    cart = Cart.query.filter_by(customer_id=customer_id).first()
    if not cart:
        return jsonify({"message": "Cart not found"}), 404

    CartItem.query.filter_by(cart_id=cart.cart_id).delete()
    # Delete the cart itself
    db.session.delete(cart)
    db.session.commit()
    return jsonify({"message": "Cart cleared"}), 200
@app.route('/orders', methods=['POST'])
def create_order():
    try:
        data = request.get_json()

        # Validate incoming data
        if not data:
            print("Error: No data received")
            return jsonify({'error': 'No data provided'}), 400

        customer_id = data.get('customer_id')
        items = data.get('items')

        if not customer_id or not items:
            print("Error: Missing customer_id or items")
            return jsonify({'error': 'Missing customer_id or items'}), 400

        print(f"Creating order for customer_id: {customer_id}")
        print(f"Items: {items}")

        # Create the order
        order = Order(customer_id=customer_id, status="Pending", total_amount=0)
        db.session.add(order)
        db.session.flush()  # Get order_id before committing

        total = 0

        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)

            if not product_id or quantity <= 0:
                print(f"Invalid product_id or quantity: {item}")
                db.session.rollback()
                return jsonify({'error': 'Invalid product_id or quantity'}), 400

            product = Product.query.get(product_id)
            if not product:
                print(f"Product with ID {product_id} not found")
                db.session.rollback()
                return jsonify({'error': f"Product with ID {product_id} not found"}), 404

            print(f"Adding product {product.name} × {quantity} to order")

            order_item = OrderItem(
                order_id=order.order_id,
                product_id=product.product_id,
                quantity=quantity,
                unit_price=product.price
            )
            db.session.add(order_item)
            total += product.price * quantity

        # Update total and commit order
        order.total_amount = total

        # Clear the customer's cart
        cart = Cart.query.filter_by(customer_id=customer_id).first()
        if cart:
            print(f"Clearing cart for customer_id: {customer_id}")
            CartItem.query.filter_by(cart_id=cart.cart_id).delete()
            db.session.delete(cart)

        db.session.commit()

        print(f"Order {order.order_id} created successfully")

        return jsonify({
            'order_id': order.order_id,
            'customer_id': order.customer_id,
            'status': order.status,
            'total_amount': total
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error occurred while creating order: {e}")
        return jsonify({'error': 'An internal error occurred while creating the order'}), 500

@app.route('/orders/<int:order_id>', methods=['GET'])
def check_order_status(order_id):
    print(f"Checking order status for order_id: {order_id}")
    order = db.session.get(Order, order_id)  # Get Order by order_id

    if not order:
        return jsonify({'error': 'Order not found'}), 404
    print("status:",order.status)
    print("customer:", order.customer_id)
    return jsonify({
        'order_id': order.order_id,
        'customer_id': order.customer_id,
        'status': order.status,
        'total': order.total_amount,
        'order_date': order.order_date.isoformat() if order.order_date else None
    })
@app.route('/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    #customer = Customer.query.get(customer_id)
    print("looking for name",customer_id)
    customer = db.session.get(Customer, customer_id)
    print("looking for name")

    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    return jsonify({
        'customer_id': customer.customer_id,
        'name': customer.first_name
    }), 200

@app.route('/api/send-email', methods=['POST'])
def save_contact_message():
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    if not name or not email or not message:
        return jsonify({'error': 'Missing data'}), 400

    # Create and save a new contact message record
    contact_msg = ContactMessage(name=name, email=email, message=message)
    db.session.add(contact_msg)
    db.session.commit()

    return jsonify({'message': 'Message saved successfully'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1200, debug=True)