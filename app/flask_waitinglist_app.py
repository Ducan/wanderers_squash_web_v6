import json
import os
from flask import Blueprint, jsonify, request, session
from app.dbconnection import (
    get_member_email_and_memnumber,
    ensure_waitinglist_internet_type,
    log_waitinglist_update,
)
from app.flask_mail_app import send_booking_cancellation_email
from datetime import datetime, timedelta

# Define the blueprint
waitinglist_bp = Blueprint('waitinglist', __name__, url_prefix='/waitinglist')

# Path to the JSON file for storing waiting list data
WAITING_LIST_FILE = os.path.join('app', 'static', 'waiting_list.json')

# Ensure the file exists
if not os.path.exists(WAITING_LIST_FILE):
    with open(WAITING_LIST_FILE, 'w') as f:
        json.dump({}, f)

def load_waiting_list():
    """Load the waiting list data from the JSON file."""
    if not os.path.exists(WAITING_LIST_FILE) or os.stat(WAITING_LIST_FILE).st_size == 0:
        return {}
    with open(WAITING_LIST_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_waiting_list(data):
    """Save the waiting list data to the JSON file."""
    with open(WAITING_LIST_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def cleanup_waiting_list():
    """
    Cleanup waiting list data by removing entries with dates before today.
    Retains entries for today and future dates.
    """
    try:
        waiting_list = load_waiting_list()  # Load the current waiting list
        current_date = datetime.now().date()  # Get today's date

        cleaned_waiting_list = {}

        # Iterate through the dates in the waiting list
        for date_str, time_slots in waiting_list.items():
            try:
                # Parse the date string (dd/MM/yyyy) to a date object
                date_obj = datetime.strptime(date_str, "%d/%m/%Y").date()

                # Keep entries that are today or in the future
                if date_obj >= current_date:
                    cleaned_waiting_list[date_str] = time_slots
                else:
                    print(f"Removing past date: {date_str}")
            except ValueError as e:
                print(f"Skipping invalid date format ({date_str}): {e}")

        # Save the cleaned waiting list back to the file
        save_waiting_list(cleaned_waiting_list)
        print("Waiting list cleanup complete. Past entries removed.")
    except Exception as e:
        print(f"Error during waiting list cleanup: {e}")

@waitinglist_bp.route('/add', methods=['POST'])
def add_to_waiting_list():
    """
    Add a player to the waiting list for a specific time slot.
    Also triggers cleanup to ensure file is up-to-date.
    """
    audit_activity = 651  # Default to error/deleted
    audit_message = "Unknown error occurred."  # Default message

    try:
        if 'Mem_No' not in session:
            audit_message = "Unauthorized: No session found."
            raise ValueError(audit_message)

        player_id = session['Mem_No']
        first_name = session.get('first_name', 'Unknown')
        last_name = session.get('last_name', 'Unknown')
        data = request.json
        date = data.get('date')  # e.g., "18/12/2024" or "2024-12-18"
        time_slot = data.get('time_slot')  # e.g., "10:30"

        if not date or not time_slot:
            audit_message = "Missing required fields: date or time_slot."
            raise ValueError(audit_message)

        # Convert date to "dd/MM/yyyy" format if needed
        try:
            date = datetime.strptime(date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass  # Assume date is already in dd/mm/yyyy format

        # Retrieve member data
        member_data = get_member_email_and_memnumber(username=player_id)
        if not member_data:
            audit_message = "User information not found."
            raise ValueError(audit_message)

        email_address = member_data.get("email")
        if not email_address or email_address.strip() == "":
            audit_message = "Please update email address in My Profile."
            raise ValueError(audit_message)

        if email_address.count('@') != 1:
            audit_message = "Invalid email address format."
            raise ValueError(audit_message)

        # Cleanup past entries before adding a new one
        cleanup_waiting_list()

        # Load the waiting list after cleanup
        waiting_list = load_waiting_list()
        if date not in waiting_list:
            waiting_list[date] = {}

        if time_slot not in waiting_list[date]:
            waiting_list[date][time_slot] = []

        # Check if the player is already in the waiting list
        for entry in waiting_list[date][time_slot]:
            if entry['player_id'] == player_id:
                # Return a flag indicating the player is already on the waiting list
                return jsonify({
                    "message": "Player already in waiting list.",
                    "already_in_list": True
                }), 200

        # Add the player to the waiting list
        waiting_list[date][time_slot].append({
            "player_id": player_id,
            "first_name": first_name,
            "last_name": last_name,
            "email_address": email_address,
            "status": "active"
        })
        save_waiting_list(waiting_list)

        audit_activity = 650  # Success
        audit_message = "Successfully added to waiting list."

        # Include email_address in the response
        return jsonify({"message": audit_message, "email_address": email_address}), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except Exception as e:
        audit_message = str(e)
        return jsonify({"error": "An unexpected error occurred."}), 500

    finally:
        try:
            # Ensure waiting list InternetType entries exist in the database
            if not ensure_waitinglist_internet_type():
                print("Warning: Failed to ensure InternetType entries for waiting list.")

            # Log the audit information
            log_waitinglist_update(
                mem_no=player_id if 'player_id' in locals() else None,
                court_date=f"{date} {time_slot}" if 'date' in locals() and 'time_slot' in locals() else datetime.now().strftime("%d/%m/%Y %H:%M"),
                first_name=first_name if 'first_name' in locals() else "Unknown",
                last_name=last_name if 'last_name' in locals() else "Unknown",
                activity=audit_activity
            )
        except Exception as log_error:
            print(f"Error logging waiting list update: {log_error}")


@waitinglist_bp.route('/remove', methods=['POST'])
def remove_from_waiting_list():
    """
    Remove a player from the waiting list for a specific time slot.
    """
    try:
        if 'Mem_No' not in session:
            return jsonify({"error": "Unauthorized: No session found."}), 401

        player_id = str(session['Mem_No'])  # Ensure player_id is always a string
        data = request.json
        date = data.get('date')
        time_slot = data.get('time_slot')

        print(f"Remove Request - Player ID: {player_id}, Date: {date}, Time Slot: {time_slot}")

        if not date or not time_slot:
            return jsonify({"error": "Missing required fields: date or time_slot."}), 400

        waiting_list = load_waiting_list()

        # Check if the date and time slot exist in the waiting list
        if date in waiting_list and time_slot in waiting_list[date]:
            # Filter out the player from the time slot
            updated_entries = [
                entry for entry in waiting_list[date][time_slot]
                if str(entry.get('player_id')) != player_id
            ]

            if updated_entries:
                waiting_list[date][time_slot] = updated_entries
            else:
                del waiting_list[date][time_slot]  # Remove the time slot if no entries remain

            # Remove the date if it has no time slots left
            if not waiting_list[date]:
                del waiting_list[date]

            save_waiting_list(waiting_list)
            print(f"Updated waiting list after removal: {waiting_list}")
            return jsonify({"message": "Successfully removed from waiting list."}), 200
        else:
            print(f"Player ID {player_id} not found for date {date} and time slot {time_slot}")
            return jsonify({"error": "Player not found in the waiting list for the specified time slot."}), 404

    except Exception as e:
        print(f"Error during removal: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@waitinglist_bp.route('/get', methods=['GET'])
def get_waiting_list():
    """
    Retrieve the waiting list for a specific date and time slot.
    """
    date = request.args.get('date')
    time_slot = request.args.get('time_slot')

    if not date or not time_slot:
        return jsonify({"error": "Missing required fields: date or time_slot"}), 400

    waiting_list = load_waiting_list()
    slots = waiting_list.get(date, {}).get(time_slot, [])

    return jsonify({"waiting_list": slots}), 200

def process_waiting_list_notifications(date, time_slot, canceling_player_id=None):
    """
    Process waiting list notifications for the given date and time slot.
    Excludes the player who initiated the cancellation from notifications.

    :param date: The date of the canceled booking.
    :param time_slot: The time slot of the canceled booking.
    :param canceling_player_id: The Mem_No of the player canceling the booking.
    """
    print(f"[INFO] Processing waiting list notifications for {date} at {time_slot}")

    waiting_list = load_waiting_list()

    # Strip seconds from time_slot for accurate comparison
    time_slot = time_slot[:5]
    print(f"[DEBUG] Adjusted time slot for comparison: {time_slot}")

    # Check if entries exist for the date and adjusted time slot
    if date in waiting_list and time_slot in waiting_list[date]:
        updated_entries = []  # To store remaining waiting list entries

        for entry in waiting_list[date][time_slot]:
            player_id = entry.get("player_id")
            email = entry.get("email_address")
            first_name = entry.get("first_name")
            last_name = entry.get("last_name")

            # Skip the player who canceled the booking
            if player_id == canceling_player_id:
                print(f"[INFO] Skipping notification for player ID {player_id} (cancelling user).")
                updated_entries.append(entry)  # Keep them in the waiting list
                continue

            if email and first_name and last_name:
                try:
                    # Send the cancellation notification email
                    print(f"[INFO] Sending email to {email} for {date} at {time_slot}")
                    send_booking_cancellation_email(
                        recipient=email,
                        F_Lastname=f"{first_name}",
                        date=date,
                        time_slot=time_slot
                    )
                    print(f"[INFO] Email sent to {email} for waiting list notification.")
                except Exception as e:
                    print(f"[ERROR] Failed to send email to {email}: {e}")
                    updated_entries.append(entry)  # Keep the entry if email fails

        # Update the waiting list (keep only non-processed entries)
        if updated_entries:
            waiting_list
            [date][time_slot] = updated_entries
        else:
            del waiting_list[date][time_slot]  # Remove the time slot if all entries are processed

        save_waiting_list(waiting_list)
        print(f"[INFO] Updated waiting list for {date} at {time_slot}.")
    else:
        print(f"[INFO] No entries found for {date} at {time_slot}.")

