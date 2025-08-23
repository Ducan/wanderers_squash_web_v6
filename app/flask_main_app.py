from flask import Blueprint, render_template, session, redirect, url_for, current_app, jsonify
from datetime import datetime
# from app.dbconnection import get_courts_descriptions, get_time_slots, get_squash_members_profile

# Create a Blueprint for the main functionality
main_bp = Blueprint('main', __name__)

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
@main_bp.before_app_request
def update_last_active():
    """
    Updates the 'last_active' timestamp in the session for every request.
    If the session is expired, clears the session and redirects to the login page.
    """
    if 'Mem_No' in session:
        print(f"Session data before update: {session}")  # Debugging
        if is_session_expired():
            print("Session expired. Clearing session.")
            session.clear()
            return redirect(url_for('login.index'))
        session['last_active'] = datetime.now().isoformat()
        print(f"Session data after update: {session}")  # Debugging
    else:
        print("No active session found.")

# Main page route
@main_bp.route('/', methods=['GET'])
def main_page():
    """
    Renders the main page if the user is logged in; otherwise redirects to the login page.
    """
    if 'Mem_No' in session:
        return render_template('main.html', user={
            "first_name": session.get("first_name"),
            "last_name": session.get("last_name"),
            "credit": session.get("credit")
        })
    else:
        print("Redirecting to login. No active session.")
        return redirect(url_for('login.index'))

# API route to provide session information
@main_bp.route('/session_info', methods=['GET'])
def session_info():
    """
    API endpoint to provide session details for the logged-in user.
    """
    if 'Mem_No' in session:
        return jsonify({
            "Mem_No": session.get('Mem_No'),
            "first_name": session.get('first_name'),
            "last_name": session.get('last_name'),
            "credit": session.get("credit")
        })
    return jsonify({"error": "No active session"}), 401