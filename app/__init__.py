# Initialize various Flask application files
from flask import Flask
from app.flask_mail_app import init_mail  # Import the mail initialization function
from app.dbconnection import close_db_connections
import atexit
import os
from dotenv import load_dotenv  # Import dotenv to load environment variables

# Import the blueprints
from app.flask_login_app import login_bp
from app.flask_main_app import main_bp
from app.flask_courts_app import courts_bp
from .flask_myprofile_app import myprofile_bp
from app.flask_timezone_app import timezone_bp, get_current_time
from .flask_periods_app import periods_bp
from app.flask_financials_app import financials_bp
from app.flask_bookings_app import bookings_bp
from app.flask_mail_app import mail_bp
from app.flask_waitinglist_app import waitinglist_bp
from app.flask_faq_app import faq_bp

def create_app():
    """
    Application factory to create and initialize the Flask app.
    Database connections use pyODBC's built-in pooling. Connections remain open
    between requests and are closed when the application shuts down to avoid
    overhead.  This function allows multiple configurations (e.g., production,
    testing) to be managed more flexibly.
    """

    # Load environment variables from .env file
    load_dotenv('environmentvariables.env')

    app = Flask(__name__)

    # Load the secret key from environment variables
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')

    # Raise an error if the secret key is not set
    if not app.config['SECRET_KEY']:
        raise ValueError("No SECRET_KEY set for Flask application. Please check environmentvariables.env.")


    # Configure session-related settings
    app.config['SESSION_TYPE'] = 'filesystem'  # Storing session data in the filesystem
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True for production
    app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cookies in same-site navigation
    app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 30 minutes session timeout. Change for live to 5 min (300)

    # Warn for development purposes if HTTPS is not used
    if app.config['SESSION_COOKIE_SECURE'] is False:
        print("Warning: SESSION_COOKIE_SECURE is set to False. Use HTTPS in production!")

    # Make the get_current_time function globally available to templates
    app.jinja_env.globals['get_current_time'] = get_current_time

    # Initialize Flask-Mail
    init_mail(app)
    
    # Register blueprints with appropriate URL prefixes
    app.register_blueprint(login_bp)
    app.register_blueprint(main_bp, url_prefix='/main')
    app.register_blueprint(courts_bp, url_prefix='/main/courts')
    app.register_blueprint(myprofile_bp, url_prefix='/main/myprofile')
    app.register_blueprint(timezone_bp)
    app.register_blueprint(periods_bp, url_prefix='/periods')
    app.register_blueprint(financials_bp, url_prefix='/financials')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(mail_bp, url_prefix='/mail')
    app.register_blueprint(waitinglist_bp, url_prefix='/waitinglist')
    app.register_blueprint(faq_bp, url_prefix='/main/faq')

    # Close database connections when the application context ends. Connections
    # are pooled and reused between requests, so shutting them down only at
    # application exit avoids unnecessary churn.
    @app.teardown_appcontext
    def teardown_appcontext(exception=None):
        close_db_connections()

    atexit.register(close_db_connections)

    if app.config.get("TESTING"):
        @app.teardown_request
        def teardown_request(exception=None):
            close_db_connections()

    return app