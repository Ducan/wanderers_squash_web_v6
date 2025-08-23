from flask import Blueprint, request, render_template, redirect, url_for, session, current_app, make_response
from datetime import datetime
from app.dbconnection import (
    get_member_profile_and_auth,
    log_internet_login,
    ensure_login_internet_type  # Import the new function
)

# Create a Blueprint for the login functionality
login_bp = Blueprint('login', __name__)

# Helper function to check session expiration
def is_session_expired():
    """
    Checks whether the session has expired based on the "last_active" timestamp.
    """
    last_active = session.get('last_active')
    if last_active:
        last_active_time = datetime.fromisoformat(last_active)
        now = datetime.now()
        return (now - last_active_time).total_seconds() > current_app.config['PERMANENT_SESSION_LIFETIME']
    return True

# Before request hook to update session activity
@login_bp.before_app_request
def update_last_active():
    """
    Updates the 'last_active' timestamp in the session for every request.
    If the session is expired, clears the session and redirects to the login page.
    """
    if 'Mem_No' in session:
        if is_session_expired():
            # Ensure the session expiration is checked
            session.clear()
            return redirect(url_for('login.index'))
        # Update 'last_active' timestamp
        session['last_active'] = datetime.now().isoformat()

# Default route to render the login page
@login_bp.route('/')
def index():
    """
    Render the login page.
    If the user is already logged in (session exists), display a welcome message with their details.
    """
    if 'Mem_No' in session:
        # If the user is already logged in, display their details
        return render_template(
            'login.html',
            welcome_message=f"Welcome back, {session['first_name']} {session['last_name']}! "
                            f"Your balance is {session['credit']}."
        )
    return render_template('login.html')

# Route to handle login form submission
@login_bp.route('/login', methods=['POST'])
def login():
    """
    Handle login requests by validating the provided username and password.
    Retrieve additional user profile details (e.g., first name, last name, and credit balance) upon successful login.
    Log the login information into the Internetlog table.
    Ensure that the login-related InternetType entry exists in the Status.mdb database.
    """
    username = request.form.get('username')
    password = request.form.get('password')

    # Clear any existing sessions before logging in
    session.clear()

    # Handle missing username or password
    if not username or not password:
        return render_template('login.html', error='Username or password is missing')

    user_profile = None
    try:
        # Retrieve profile and validate credentials
        user_profile = get_member_profile_and_auth(username, password)

        if not user_profile:
            return render_template('login.html', error='Invalid username or password')

        # Check if the user is blocked
        blocked_status = int(user_profile.get('blocked', 0))
        if blocked_status != 0:
            return render_template('login.html', error='Login blocked. Contact Squash Committee')

        # User is authenticated; store details in session
        session['Mem_No'] = user_profile['member_no']
        session.permanent = True  # Ensures session respects the configured lifetime
        session['first_name'] = user_profile['first_name']
        session['last_name'] = user_profile['surname']
        session['credit'] = user_profile['credit']
        session['last_active'] = datetime.now().isoformat()

        # Ensure login-related InternetType entry exists
        if not ensure_login_internet_type():
            print("Failed to ensure the InternetType entry exists. Proceeding anyway...")

        # Redirect to the main page after successful login **without storing login page in history**
        response = make_response(redirect(url_for('main.main_page')))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"An error occurred during login: {e}")
        return render_template('login.html', error='An internal error occurred. Please try again later.')
    finally:
        # Log the login information into the Internetlog table with activity code 600
        try:
            if user_profile:
                log_internet_login(
                    mem_no=int(user_profile['member_no']),
                    court_date=datetime.now().strftime("%d/%m/%Y %H:%M"),
                    first_name=user_profile['first_name'],
                    last_name=user_profile['surname'],
                    activity=600  # Activity code for Internet login - Successful
                )
                print("Login information successfully logged.")
        except Exception as log_error:
            print(f"Error logging login audit: {log_error}")

# Route to display the main page after login
@login_bp.route('/main')
def main_page():
    """
    Display the main page with the user's details after login.
    If the user is not logged in, redirect them to the login page.
    """
    if 'Mem_No' in session:
        return f"Welcome, {session['first_name']} {session['last_name']}! Your balance is {session['credit']}."
    return redirect(url_for('login.index'))

# Route to handle user logout
@login_bp.route('/logout', methods=['GET'])
def logout():
    """
    Clears the user's session and redirects to the login page.
    """
    session.clear()  # Clear all session data
    print("User logged out and session cleared.")  # Optional debug statement
    return redirect(url_for('login.index'))  # Redirect to the login page