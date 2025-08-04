from flask import Blueprint, render_template, flash, send_from_directory, redirect
from flask_login import login_required, current_user
from .forms import ShopItemsForm, OrderForm
from werkzeug.utils import secure_filename
from .models import Product, Order, Customer,Category
from . import db


admin = Blueprint('admin', __name__)


@admin.route('/media/<path:filename>')
def get_image(filename):
    return send_from_directory('../media', filename)


@admin.route('/add-shop-items', methods=['GET', 'POST'])
@login_required
def add_shop_items():
    if current_user.usertype == 1:
        form = ShopItemsForm()
        form.category_id.choices = [(c.category_id, c.name) for c in Category.query.all()]


        if form.validate_on_submit():
            name = form.name.data
            price = form.price.data
            stock_quantity = form.stock_quantity.data
            category_id = form.category_id.data
            file = form.product_picture.data

            file_name = secure_filename(file.filename)
            file_path = f'./media/{file_name}'
            file.save(file_path)

            new_shop_item = Product(
                name=name,
                price=price,
                stock_quantity=stock_quantity,
                category_id=category_id,
                product_picture=file_path
            )

            try:
                db.session.add(new_shop_item)
                db.session.commit()
                flash(f'{name} added successfully')
                return render_template('add_shop_items.html', form=form)
            except Exception as e:
                print(e)
                flash('Product not added!!')

        return render_template('add_shop_items.html', form=form)

    return render_template('404.html')


@admin.route('/shop-items', methods=['GET', 'POST'])
@login_required
def shop_items():
    if current_user.usertype == 1:
        items = Product.query.order_by(Product.created_at.desc()).all()
        return render_template('shop_items.html', items=items)
    return render_template('404.html')


@admin.route('/update-item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def update_item(item_id):
    if current_user.usertype == 1:
        form = ShopItemsForm()

        item_to_update = Product.query.get(item_id)

        form.name.render_kw = {'placeholder': item_to_update.name}
        form.price.render_kw = {'placeholder': item_to_update.price}
        form.stock_quantity.render_kw = {'placeholder': item_to_update.stock_quantity}

        if form.validate_on_submit():
            name = form.name.data
            price = form.price.data

            stock_quantity = form.stock_quantity.data
            category_id = form.category_id.data
            file = form.product_picture.data

            file_name = secure_filename(file.filename)
            file_path = f'./media/{file_name}'

            file.save(file_path)

            try:
                Product.query.filter_by(product_id=item_id).update(dict(name=name,
                                                                price=price,
                                                                category_id=category_id,
                                                                stock_quantity=stock_quantity,
                                                                product_picture=file_path))

                db.session.commit()
                flash(f'{name} updated Successfully')
                print('Product Updated')
                return redirect('/shop-items')
            except Exception as e:
                print('Product not Upated', e)
                flash('Item Not Updated!!!')

        return render_template('update_item.html', form=form)
    return render_template('404.html')

@admin.route('/delete-item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def delete_item(item_id):
    if current_user.usertype == 1:
        try:
            item_to_delete = Product.query.get(item_id)
            db.session.delete(item_to_delete)
            db.session.commit()
            flash('One Item deleted')
            return redirect('/shop-items')
        except Exception as e:
            print('Item not deleted', e)
            flash('Item not deleted!!')
        return redirect('/shop-items')

    return render_template('404.html')


@admin.route('/view-orders')
@login_required
def order_view():
    if current_user.usertype == 1:
        orders = Order.query.all()
        return render_template('view_orders.html', orders=orders)
    return render_template('404.html')


@admin.route('/update-order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def update_order(order_id):
    if current_user.usertype == 1:
        form = OrderForm()

        order = Order.query.get(order_id)
        id = order_id
        if form.validate_on_submit():
            status = form.order_status.data

            order.status = status

            try:
                db.session.commit()
                flash(f'Order {order_id} Updated successfully')
                return redirect('/view-orders')
            except Exception as e:
                print(e)
                flash(f'Order {order_id} not updated')
                return redirect('/view-orders')

        return render_template('order_update.html', form=form,order_id=id)

    return render_template('404.html')


@admin.route('/customers')
@login_required
def display_customers():
    if current_user.usertype == 1:
        customers = Customer.query.all()
        return render_template('customers.html', customers=customers)
    return render_template('404.html')


@admin.route('/admin-page')
@login_required
def admin_page():
    if current_user.id == 1:
        return render_template('admin.html')
    return render_template('404.html')









