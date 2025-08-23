# Time Zone cofniguration
import pytz
from datetime import datetime
from flask import Blueprint, request, session, jsonify, render_template

# Blueprint for timezone-related routes
timezone_bp = Blueprint('timezone', __name__)

# Default time zone configuration
DEFAULT_TIMEZONE = 'Africa/Windhoek'
DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'

# Function to get the current time in the configured or user-provided time zone
def get_current_time():
    try:
        user_timezone = session.get('user_timezone', DEFAULT_TIMEZONE)
        tz = pytz.timezone(user_timezone)
        return datetime.now(tz).strftime(f"{DATE_FORMAT} {TIME_FORMAT}")
    except pytz.UnknownTimeZoneError:
        # Fall back to default time zone
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        return datetime.now(tz).strftime(f"{DATE_FORMAT} {TIME_FORMAT}")

# Route to set the user's time zone
@timezone_bp.route('/set-timezone', methods=['POST'])
def set_timezone():
    data = request.json
    print("Received data:", data)  # Debug log
    user_timezone = data.get('timezone')
    if user_timezone:
        try:
            pytz.timezone(user_timezone)  # Validate time zone
            session['user_timezone'] = user_timezone
            print("Time zone set to:", user_timezone)  # Debug log
            return jsonify({"message": "Time zone set successfully"}), 200
        except pytz.UnknownTimeZoneError:
            print("Invalid time zone:", user_timezone)  # Debug log
            return jsonify({"error": "Invalid time zone"}), 400
    print("Time zone not provided")  # Debug log
    return jsonify({"error": "Time zone not provided"}), 400

# Debug route to check session data
@timezone_bp.route('/debug-session', methods=['GET'])
def debug_session():
    return jsonify({"session": dict(session)})

# Route to render the test time zone page
@timezone_bp.route('/test-timezone', methods=['GET'])
def test_timezone():
    return render_template('test_timezone.html', configured_timezone=session.get('user_timezone', DEFAULT_TIMEZONE))
