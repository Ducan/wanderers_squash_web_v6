from flask_mail import Mail, Message
from flask import Blueprint, current_app, jsonify, request
from dotenv import load_dotenv
import os
import socket  # Import for DNS resolution
from datetime import datetime  # For date and time validation/formatting
from flask_mail import Mail, Message # To be removed. For testing only test_mail.py

# Load environment variables from the .env file
env_path = os.path.join(os.path.dirname(__file__), 'static', 'environmentvariables.env')
load_dotenv(env_path)

# Flask-Mail instance
mail = Mail()

# Create the mail blueprint
mail_bp = Blueprint('mail_bp', __name__)

# Subject line variables
BookingConfirmation = "Booking Confirmation"
BookingCancellation = "Booking Cancellation"

def init_mail(app):
    """
    Initialize Flask-Mail with the given Flask application instance.
    """
    app.config['MAIL_SERVER'] = 'mail.wanderers.org.na'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True

    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        raise RuntimeError("MAIL_USERNAME or MAIL_PASSWORD is not set in environmentvariables.env!")

    try:
        resolved_addresses = socket.getaddrinfo(app.config['MAIL_SERVER'], None)
        resolved_ips = [addr[4][0] for addr in resolved_addresses]
        print(f"Resolved {app.config['MAIL_SERVER']} to: {', '.join(resolved_ips)}")
    except socket.gaierror as e:
        raise RuntimeError(
            f"Failed to resolve SMTP server address {app.config['MAIL_SERVER']}: {e}"
        )

    mail.init_app(app)

def send_email(subject: str, recipients: list, body: str):
    """
    Send an email with the specified subject, recipients, and body.
    """
    if not recipients:
        raise ValueError("Recipients list cannot be empty.")

    msg = Message(
        subject=subject,
        sender=current_app.config['MAIL_USERNAME'],
        recipients=recipients,
        body=body
    )
    mail.send(msg)

@mail_bp.route('/send-email', methods=['POST'])
def send_email_endpoint():
    """
    Endpoint for sending a generic email. Accepts JSON data.
    """
    data = request.get_json()

    subject = data.get('subject')  # Subject line
    recipients = data.get('recipients')  # List of recipients
    email_body = data.get('email_body')  # Email body text

    if not all([subject, recipients, email_body]):
        return jsonify({"error": "Missing required fields: subject, recipients, email_body"}), 400

    try:
        send_email(subject=subject, recipients=recipients, body=email_body)
        return jsonify({"message": "Email sent successfully."}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {e}"}), 500


# ==========================================
# Booking Cancellation Email Function
# ==========================================
def send_booking_cancellation_email(recipient: str, F_Lastname: str, date: str, time_slot: str):
    """
    Send an email notification about a booking cancellation for a specific time slot.
    The date format must be [dd/mm/yyyy] and the time format [HH:MM].
    """
    # Validate and format the date
    try:
        formatted_date = datetime.strptime(date, "%d/%m/%Y").strftime("%d/%m/%Y")
    except ValueError:
        raise ValueError("Date format is invalid. Expected format: dd/mm/yyyy.")

    # Validate and format the time
    try:
        formatted_time = datetime.strptime(time_slot, "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError("Time format is invalid. Expected format: HH:MM.")

    # Construct subject and body using variables
    subject = BookingCancellation  # Use the predefined subject variable
    email_body = f"""
    Hi {F_Lastname},

    The following booking on the squash court waiting list has been cancelled and is now available for bookings:
        
    Details:
    - Date: {formatted_date}
    - Time Slot: {formatted_time}

    Please note that all bookings are processed on a first-come, first-served basis. Therefore, to secure a spot, make a new reservation as soon as possible.
    If the booking is no longer available, you are welcome to add yourself back to the waiting list.

    Kind regards,
    Squash Committee

    P.S: Please note that this mailbox is not being monitored, and any emails sent here will not be read or responded to.

    """

    # Call the send_email function
    send_email(subject=subject, recipients=[recipient], body=email_body)


