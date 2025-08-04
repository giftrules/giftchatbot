from flask import Blueprint, render_template, flash, redirect, request, jsonify
from mywebapp.models import Cart, CartItem, Product,Order,OrderItem
from flask_login import login_required, current_user
from . import db

views = Blueprint('views', __name__)


@views.route('/')
def home():

    items = Product.query.all()
    cart_items = []
    cart =[]
    if current_user.is_authenticated:
        cart = Cart.query.filter_by(customer_id=current_user.customer_id).first()
        if cart:
            cart_items = CartItem.query.filter_by(cart_id=cart.cart_id).all()

    return render_template('home.html', items=items, cart=cart, cart_items=cart_items)


@views.route('/contact')
def contact():

    items = Product.query.all()

    return render_template('contact_us.html')



@views.route('/add-to-cart/<int:item_id>')
@login_required
def add_to_cart(item_id):

    # Get the customer ID from the session or request (this can vary based on your app's session management)
    quantity=1
    product = Product.query.get(item_id)

    if not product:
        return jsonify({"message": "Product not found"}), 404

    # Check if the customer already has a cart
    cart = Cart.query.filter_by(customer_id=current_user.customer_id).first()
    if not cart:
        # If the customer doesn't have a cart, create one
        cart = Cart(customer_id=current_user.customer_id)
        db.session.add(cart)
        db.session.commit()

    # Check if the product is already in the cart
    cart_item = CartItem.query.filter_by(cart_id=cart.cart_id, product_id=item_id).first()
    if cart_item:
        # If the product is already in the cart, update the quantity
        cart_item.quantity += quantity
    else:
        # If the product is not in the cart, add it
        cart_item = CartItem(cart_id=cart.cart_id, product_id=item_id, quantity=quantity)
        db.session.add(cart_item)

    # Commit the transaction to the database
    db.session.commit()
    print(product.name)
    flash(f'{product.name} added to cart')
    return redirect(request.referrer)


@views.route('/cart')
@login_required
def show_cart():
    # Get the user's cart
    cart = Cart.query.filter_by(customer_id=current_user.customer_id).first()

    if not cart:
        # If the user has no cart, render empty cart
        return render_template('cart.html', cart=None)

    # Get all cart items for the cart
    cart_items = CartItem.query.filter_by(cart_id=cart.cart_id).all()

    # Calculate total amount
    amount = 0
    for item in cart_items:
        amount += item.product.price * item.quantity

    return render_template('cart.html', cart=cart_items, amount=amount, total=amount)
@views.route('/chatbox')
@login_required
def show_chartbox():
     return render_template('chat.html')


@views.route('/pluscart')
@login_required
def plus_cart():
    if request.method == 'GET':
        cart_item_id = request.args.get('cart_id')
        cart_item = CartItem.query.get(cart_item_id)

        if cart_item:
            cart_item.quantity += 1
            db.session.commit()

            cart_items = CartItem.query.filter_by(cart_id=cart_item.cart_id).all()
            amount = sum(item.product.price * item.quantity for item in cart_items)

            data = {
                'quantity': cart_item.quantity,
                'amount': amount,
                'total': amount
            }
            return jsonify(data)
        return jsonify({'error': 'Cart item not found'}), 404

@views.route('/minuscart')
@login_required
def minus_cart():
    if request.method == 'GET':
        cart_item_id = request.args.get('cart_id')
        cart_item = CartItem.query.get(cart_item_id)

        if cart_item:
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                db.session.commit()
            else:
                db.session.delete(cart_item)
                db.session.commit()

            cart_items = CartItem.query.filter_by(cart_id=cart_item.cart_id).all()
            amount = sum(item.product.price * item.quantity for item in cart_items)

            data = {
                'quantity': cart_item.quantity if cart_item in db.session else 0,
                'amount': amount,
                'total': amount
            }
            return jsonify(data)
        return jsonify({'error': 'Cart item not found'}), 404

@views.route('/removecart')
@login_required
def remove_cart():
    if request.method == 'GET':
        cart_item_id = request.args.get('cart_id')
        cart_item = CartItem.query.get(cart_item_id)

        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()

            cart_items = CartItem.query.filter_by(cart_id=cart_item.cart_id).all()
            amount = sum(item.product.price * item.quantity for item in cart_items)

            data = {
                'quantity': 0,
                'amount': amount,
                'total': amount
            }
            return jsonify(data)
        return jsonify({'error': 'Cart item not found'}), 404

@views.route('/place-order')
@login_required
def place_order():
    # Get the customer ID from the request (usually comes from the session)

    cart = Cart.query.filter_by(customer_id=current_user.customer_id).first()
    if not cart:
        flash('Your cart is Empty')
        return jsonify({"message": "Cart not found"}), 404

    # Get all the items in the cart
    cart_items = CartItem.query.filter_by(cart_id=cart.cart_id).all()
    if not cart_items:

        return redirect('/') # Cannot place an order with an empty cart

    # Create a new order for the customer
    new_order = Order(
        customer_id=current_user.customer_id,
        status="Pending",  # Initial status of the order
        total_amount=0  # We will calculate this later
    )
    db.session.add(new_order)
    db.session.commit()

    # Calculate the total amount of the order
    total_amount = 0
    for cart_item in cart_items:
        product = Product.query.get(cart_item.product_id)
        if not product:
            flash('Product not found')
            return redirect('/')

        # Add to the total amount (quantity * unit price)
        total_amount += cart_item.quantity * product.price

        # Create an order item
        order_item = OrderItem(
            order_id=new_order.order_id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            unit_price=product.price
        )
        db.session.add(order_item)

    # Update the total amount in the order
    new_order.total_amount = total_amount
    db.session.commit()

    # Clear the cart after placing the order
    CartItem.query.filter_by(cart_id=cart.cart_id).delete()
    # Delete the cart itself
    db.session.delete(cart)
    db.session.commit()

    # Respond with the order details
    return redirect('/orders')


@views.route('/orders')
@login_required
def order():
    orders = Order.query.filter_by(customer_id=current_user.customer_id).order_by(Order.order_date.desc()).all()
    return render_template('orders.html', orders=orders)









