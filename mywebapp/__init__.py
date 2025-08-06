from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
DB_NAME = 'ecommerce.db'


def create_app():

    app = Flask(__name__)
    app.config['SECRET_KEY'] = '388bcc5e0b97c052289b46abdbe1f19ea1a2ffd4d9bc4ac72509220b8c7d04a0'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html')

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Load user function
    @login_manager.user_loader
    def load_user(user_id):
        return Customer.query.get(int(user_id))

    from .views import views
    from .auth import auth
    from .admin import admin
    from .models import Customer, Cart, Product, Order
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/')
    # Initialize the database (this will create the tables in the database)
    with app.app_context():
        create_database()
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    return app

def create_database():
    db.create_all()
    print('Database Created')
    print('Good to go')