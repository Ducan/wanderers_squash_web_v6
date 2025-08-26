from flask import Blueprint, jsonify, request, session, render_template
from flask import current_app
from app.dbconnection import (
    get_squash_members_profile,
    update_internet_bookings,
    delete_internet_booking,
    log_audit_online_booking,
    get_courts_with_ids,
    update_squash_member_profile,
    get_booking_limitations,
    get_periods,
    get_booked_players_memno,
    get_period_ids_by_date_range,
    get_booking_cell,
    get_time_slots,
    DEFAULT_TIMEZONE,
   )
from app.flask_waitinglist_app import process_waiting_list_notifications
from datetime import datetime, timedelta
import pytz
import pandas as pd

# Define the blueprint for bookings
bookings_bp = Blueprint("bookings", __name__)

@bookings_bp.route('/get_user_info', methods=['GET'])
def get_user_info():
    """
    API endpoint to retrieve the first and last name of the logged-in user.
    """
    mem_no = session.get('Mem_No')  # Use correct session key
    if not mem_no:
        return jsonify({"error": "User not logged in or session expired."}), 401

    member_profile = get_squash_members_profile(username=mem_no)
    if not member_profile:
        return jsonify({"error": "Member profile not found."}), 404

    return jsonify({
        "first_name": member_profile["first_name"],
        "last_name": member_profile["surname"],
        "member_no": mem_no,
        "credit": member_profile.get("credit", 0.00)  # Include Lights Credit in the response
    })


@bookings_bp.route('/descriptions', methods=['GET'])
def get_court_descriptions_api():
    """
    API endpoint to retrieve court descriptions and corresponding Court IDs (CourtNo).
    """
    if 'Mem_No' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        descriptions_with_ids = get_courts_with_ids()
        return jsonify({"courts": descriptions_with_ids})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Booking Limitations
@bookings_bp.route('/get_booking_limitations', methods=['GET'])
def get_player_booking_limitations():
    """
    API endpoint to retrieve booking limitations for the logged-in player.
    Aligns period descriptions and IDs with daily and weekly booking limits.

    Returns:
        JSON response with booking limitations, period descriptions, IDs, or an error message.
    """
    try:
        mem_no = session.get('Mem_No')

        if not mem_no:
            return jsonify({"error": "Member number not found in session. Please log in again."}), 401

        try:
            mem_no = int(mem_no)  # Ensure mem_no is an integer
        except ValueError:
            return jsonify({"error": "Invalid member number in session."}), 400

        # Fetch booking limitations
        booking_limitations = get_booking_limitations(mem_no)

        if booking_limitations is None:
            return jsonify({"error": f"Booking limitations not found for member number {mem_no}."}), 404

        # Fetch period descriptions
        periods = get_periods()

        # Align descriptions and IDs with daily and weekly limits
        def align_descriptions(limits):
            return [
                {
                    "limit": limit,
                    "period_id": periods[i]["id"] if i < len(periods) else None,
                    "period_description": periods[i]["description"] if i < len(periods) else "Unknown"
                }
                for i, limit in enumerate(limits)
            ]

        aligned_daily_limits = align_descriptions(booking_limitations["daily_limits"])
        aligned_weekly_limits = align_descriptions(booking_limitations["weekly_limits"])

        # Construct the response
        response = {
            "mem_no": int(booking_limitations.pop("mem_no")),  # Ensure mem_no is an integer without decimals
            "status": "success",
            "data": {
                "daily_limits": aligned_daily_limits,
                "weekly_limits": aligned_weekly_limits
            }
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve booking limitations: {str(e)}"}), 500

# Booking limits for daily
@bookings_bp.route('/booking_daily_limits', methods=['GET'])
def check_daily_booking_limits():
    """
    API endpoint to check daily booking limits for the logged-in player.
    Aligns daily booking limits with periods.

    Query Parameters:
        - date: Date to check (dd/MM/yyyy).

    Returns:
        JSON response with status, period-aligned booking limits, and validation results.
    """
    try:
        mem_no = session.get('Mem_No')

        if not mem_no:
            return jsonify({"error": "Member number not found in session. Please log in again."}), 401

        try:
            mem_no = int(mem_no)  # Ensure mem_no is an integer
        except ValueError:
            return jsonify({"error": "Invalid member number in session."}), 400

        # Retrieve query parameter
        date = request.args.get('date')

        if not date:
            return jsonify({"error": "Missing date parameter."}), 400

        # Validate and parse date
        try:
            datetime.strptime(date, "%d/%m/%Y")
        except ValueError:
            return jsonify({"error": "Invalid date format. Expected format: dd/MM/yyyy."}), 400

        # Fetch bookings for the specified date
        bookings_data = get_booked_players_memno(date, date)

        if bookings_data.empty:
            return jsonify({
                "status": "success",
                "message": "No bookings found for the specified date.",
                "bookings_count": 0,
                "limits": []
            }), 200

        # Fetch daily booking limits for the player
        booking_limitations = get_booking_limitations(mem_no)
        if not booking_limitations or not booking_limitations.get('daily_limits'):
            return jsonify({"error": "Daily booking limitations not found for this player."}), 404

        daily_limits = booking_limitations['daily_limits']

        # Fetch periods for the specified date
        period_data = get_period_ids_by_date_range(date, date)

        # Fetch periods from the system
        periods = get_periods()

        # Align daily limits with periods by period_id
        aligned_daily_limits = [
            {
                "limit": limit,
                "period_id": period["id"],
                "period_description": period["description"],
                "bookings_count": 0  # Initialize booking count
            }
            for limit, period in zip(daily_limits, periods)
        ]

        # Debugging aligned_daily_limits structure
        print(f"[DEBUG] Aligned Daily Limits Before Processing: {aligned_daily_limits}")

        # Count bookings per period
        for booking in bookings_data.itertuples():
            try:
                # Parse StartTime and check if it is in the future
                booking_datetime = datetime.strptime(booking.StartTime, "%d/%m/%Y %H:%M:%S")
                if booking_datetime < datetime.now() and date == datetime.now().strftime("%d/%m/%Y"):
                    print(f"[DEBUG] Skipping Past Booking: Date={booking.Date}, Time={booking.StartTime}")
                    continue

                # Format the time for comparison
                formatted_time = booking_datetime.strftime("%H:%M")
            except ValueError:
                print(f"[ERROR] Invalid StartTime format: {booking.StartTime}")
                continue

            print(f"[DEBUG] Processing Booking: Date={booking.Date}, Time={formatted_time}, PlayerNos={booking.PlayerNos}")

            for period_entry in period_data:
                if (
                    period_entry["date"] == booking.Date
                    and period_entry["time"] == formatted_time
                ):
                    player_nos = [p.strip() for p in booking.PlayerNos.split(",")]
                    print(f"[DEBUG] Match Found: Date={booking.Date}, Time={formatted_time}, PlayerNos={player_nos}, Periods={period_entry['periods']}")

                    for idx, period_id in enumerate(period_entry["periods"]):
                        if idx < len(player_nos) and player_nos[idx] != "None" and str(mem_no) == player_nos[idx]:
                            # Find the correct entry in aligned_daily_limits
                            for limit in aligned_daily_limits:
                                if limit["period_id"] == period_id:
                                    limit["bookings_count"] += 1
                                    print(f"[DEBUG] Incremented Count: Period ID={period_id}, Description={limit['period_description']}, Count={limit['bookings_count']}")
                                    break

        # Check if any period exceeds its limit
        exceeded_periods = [
            limit for limit in aligned_daily_limits
            if limit["bookings_count"] > limit["limit"]
        ]

        # Response
        if exceeded_periods:
            return jsonify({
                "status": "failed",
                "message": "Daily booking limit exceeded for one or more periods.",
                "limits": aligned_daily_limits
            }), 403

        return jsonify({
            "status": "success",
            "message": "Daily booking limit is within bounds.",
            "limits": aligned_daily_limits
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to validate daily booking limits: {str(e)}"}), 500


# Booking limits for weekly
@bookings_bp.route('/booking_weekly_limits', methods=['GET'])
def check_weekly_booking_limits():
    """
    API endpoint to check weekly booking limits for the logged-in player.
    Weekly limits are calculated for the week defined by start_date and end_date.

    Query Parameters:
        - start_date: Start date of the week (dd/MM/yyyy).
        - end_date: End date of the week (dd/MM/yyyy).

    Returns:
        JSON response with status, period-aligned booking limits, and validation results.
    """
    try:
        mem_no = session.get('Mem_No')

        if not mem_no:
            return jsonify({"error": "Member number not found in session. Please log in again."}), 401

        try:
            mem_no = int(mem_no)  # Ensure mem_no is an integer
        except ValueError:
            return jsonify({"error": "Invalid member number in session."}), 400

        # Retrieve query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify({"error": "Missing start_date or end_date parameters."}), 400

        # Validate and parse dates
        try:
            start_date_dt = datetime.strptime(start_date, "%d/%m/%Y")
            end_date_dt = datetime.strptime(end_date, "%d/%m/%Y")
        except ValueError:
            return jsonify({"error": "Invalid date format. Expected format: dd/MM/yyyy."}), 400

        # Ensure start_date and end_date define a valid week
        if start_date_dt > end_date_dt:
            return jsonify({"error": "start_date cannot be after end_date."}), 400

        # Fetch bookings for the specified week
        bookings_data = get_booked_players_memno(start_date, end_date)

        if bookings_data.empty:
            return jsonify({
                "status": "success",
                "message": "No bookings found within the specified week.",
                "bookings_count": 0,
                "limits": []
            }), 200

        # Fetch weekly booking limits for the player
        booking_limitations = get_booking_limitations(mem_no)
        if not booking_limitations or not booking_limitations.get('weekly_limits'):
            return jsonify({"error": "Weekly booking limitations not found for this player."}), 404

        weekly_limits = booking_limitations['weekly_limits']

        # Fetch periods for the specified week
        period_data = get_period_ids_by_date_range(start_date, end_date)

        # Fetch periods from the system
        periods = get_periods()

        # Align weekly limits with periods by period_id
        aligned_weekly_limits = [
            {
                "limit": limit,
                "period_id": period["id"],
                "period_description": period["description"],
                "bookings_count": 0  # Initialize booking count
            }
            for limit, period in zip(weekly_limits, periods)
        ]

        # Count bookings per period
        for booking in bookings_data.itertuples():
            try:
                # Parse StartTime, include bookings for the current day in the past
                booking_datetime = datetime.strptime(booking.StartTime, "%d/%m/%Y %H:%M:%S")
                formatted_time = booking_datetime.strftime("%H:%M")
            except ValueError:
                print(f"[ERROR] Invalid StartTime format: {booking.StartTime}")
                continue

            for period_entry in period_data:
                if (
                    period_entry["date"] == booking.Date
                    and period_entry["time"] == formatted_time
                ):
                    player_nos = [p.strip() for p in booking.PlayerNos.split(",")]
                    for idx, period_id in enumerate(period_entry["periods"]):
                        if idx < len(player_nos) and player_nos[idx] != "None" and str(mem_no) == player_nos[idx]:
                            # Find the correct entry in aligned_weekly_limits
                            for limit in aligned_weekly_limits:
                                if limit["period_id"] == period_id:
                                    limit["bookings_count"] += 1
                                    break

        # Check if any period exceeds its limit
        exceeded_periods = [
            limit for limit in aligned_weekly_limits
            if limit["bookings_count"] > limit["limit"]
        ]

        # Response
        if exceeded_periods:
            return jsonify({
                "status": "failed",
                "message": "Weekly booking limit exceeded for one or more periods.",
                "limits": aligned_weekly_limits
            }), 403

        return jsonify({
            "status": "success",
            "message": "Weekly booking limit is within bounds.",
            "limits": aligned_weekly_limits
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to validate weekly booking limits: {str(e)}"}), 500




# Create a booking
@bookings_bp.route('/add', methods=['POST'])
def add_booking():
    """
    Handle adding a booking as a two-step process:
    1. Perform the booking operation.
    2. If successful, call add_booking_financials.
    """
    try:
        # Step 1: Parse incoming data
        data = request.json
        player_no = data.get("player_no")
        date_container = data.get("date_container")  # Expected "YYYY-MM-DD"
        slot_id = data.get("slot_id")
        selected_court = data.get("selected_court")

        if not (player_no and date_container and slot_id and selected_court):
            return jsonify({"error": "Missing required booking details."}), 400

        try:
            booking_date = datetime.strptime(date_container, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format. Expected 'YYYY-MM-DD'."}), 400

        # Determine day of week for time slot retrieval (1=Sunday,...,7=Saturday)
        py_day = booking_date.weekday()  # 0=Mon
        day_of_week = py_day + 2
        if day_of_week == 8:
            day_of_week = 1

        time_slots = get_time_slots(day_of_week)
        try:
            slot_index = int(slot_id) - 1
            selected_time = time_slots[slot_index]
        except (ValueError, IndexError):
            return jsonify({"error": "Invalid slot ID."}), 400

        local_tz = pytz.timezone(DEFAULT_TIMEZONE)
        booking_time = local_tz.localize(
            datetime.strptime(f"{date_container} {selected_time}", "%Y-%m-%d %H:%M")
        )
        end_time = booking_time + timedelta(minutes=45)
        if booking_time < datetime.now(local_tz):
            return jsonify({"error": "Bookings cannot be made for past time slots."}), 403

        date_container_formatted = booking_date.strftime("%d/%m/%Y")
        booking_time_str = f"{date_container_formatted} {selected_time}:00"

        # Step 2: Validate Lights Credit
        user_profile = get_squash_members_profile(username=player_no)
        if not user_profile:
            return jsonify({"error": "User profile not found."}), 404

        lights_credit = float(user_profile.get("credit", 0.00))
        if lights_credit <= 0.00:
            return jsonify({"error": "Booking not allowed. Insufficient Lights Credit (0.00 or below)."}), 403

        # Step 3: Check slot availability then perform the booking
        player_no_column = f"PlayerNo_{selected_court}"
        existing = get_booking_cell(booking_time_str, player_no_column)
        # Only treat slots as booked if they contain a value other than None, -9 or 0
        if existing not in (None, -9, 0):
            return jsonify({"status": "already_booked", "message": "Slot already booked."}), 409

        result = update_internet_bookings(
            date_container=date_container_formatted,
            mem_no=player_no,
            selected_court={"player_no_column": player_no_column},
            selected_time=selected_time
        )

        if result.get("status") == "already_booked":
            return jsonify({"status": "already_booked", "message": "Slot already booked."}), 409
        if result.get("status") != "success":
            return jsonify({"error": "Failed to save booking. No matching row found."}), 404

        # Step 4: Call the financial update
        financial_result = add_booking_financials(player_no)
        if financial_result["status"] == "error":
            return jsonify({"message": "Booking saved, but financial update failed.", "error": financial_result["message"]}), 500

        # Step 5: Update session credit
        updated_credit = financial_result["financial_data"]["updated_credit"]
        session['credit'] = updated_credit

        return jsonify({
            "message": "Booking successfully saved.",
            "financial_data": financial_result["financial_data"],
            "updated_credit": updated_credit  # Include the updated credit in the response
        }), 200
    
    finally:
        try:
            # Log the audit information
            log_audit_online_booking(
                mem_no=player_no if 'player_no' in locals() else None,
                court_date=booking_time_str if 'booking_time_str' in locals() else datetime.now().strftime("%d/%m/%Y %H:%M"),
                court=selected_court if 'selected_court' in locals() else "Unknown",
                first_name=session.get('first_name', "Unknown"),
                last_name=session.get('last_name', "Unknown"),
                activity=1  # Hardcoded for successful booking
            )

        except Exception as e:
            return jsonify({"error": str(e)}), 500


def add_booking_financials(player_no):
    try:
        financial_payload = {"mem_no": player_no, "cost_type": "IBOOKING"}
        print(f"[DEBUG] Financial payload for booking: {financial_payload}")

        financial_endpoint = f"{request.host_url}financials/calculated_internet_bookings".rstrip("/")
        print(f"[DEBUG] Financial endpoint URL: {financial_endpoint}")

        # Use current_app for test client
        with current_app.test_client() as client:
            financial_response = client.post(
                financial_endpoint,
                json=financial_payload,
                follow_redirects=True,
            )

        if financial_response.status_code == 200:
            financial_data = financial_response.get_json()
            updated_credit = financial_data.get("updated_credit")

            # Persist updated S_Credit to the database
            member_profile = get_squash_members_profile(username=player_no)
            if member_profile:
                update_success = update_squash_member_profile(
                    member_no=player_no,
                    first_name=member_profile["first_name"],
                    last_name=member_profile["surname"],
                    cell_phone=member_profile["cell_phone"],
                    email=member_profile["email"],
                    credit=updated_credit
                )
                if not update_success:
                    return {"status": "error", "message": "Failed to update S_Credit in the database."}

            return {"status": "success", "financial_data": financial_data}
        else:
            return {"status": "error", "message": f"Financial API failed. Response: {financial_response.text}"}
    except Exception as e:
        print(f"[ERROR] Exception in add_booking_financials: {e}")
        return {"status": "error", "message": str(e)}


# Delete Internet Bookings
@bookings_bp.route('/delete', methods=['POST'])
def delete_booking():
    """
    Handle deletion of a booking as a two-step process:
    1. Perform the cancellation operation.
    2. Notify users on the waiting list.
    """
    try:
        # Step 1: Retrieve data from the request
        data = request.json
        date_container = data.get("date_container")  # "YYYY-MM-DD"
        slot_id = data.get("slot_id")
        player_no_column = data.get("player_no_column")  # e.g., "PlayerNo_1"
        player_no = data.get("player_no")  # Member number
        selected_court = data.get("selected_court")  # Court ID or number
        period_id = data.get("period_id")  # Booking period identifier

        if not (date_container and slot_id and player_no_column and player_no and selected_court and period_id):
            return jsonify({"error": "Missing booking details."}), 400

        try:
            booking_date = datetime.strptime(date_container, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format. Expected 'YYYY-MM-DD'."}), 400

        py_day = booking_date.weekday()
        day_of_week = py_day + 2
        if day_of_week == 8:
            day_of_week = 1
        time_slots = get_time_slots(day_of_week)
        try:
            slot_index = int(slot_id) - 1
            selected_time = time_slots[slot_index]
        except (ValueError, IndexError):
            return jsonify({"error": "Invalid slot ID."}), 400

        date_formatted = booking_date.strftime("%d/%m/%Y")
        start_time1 = f"{date_formatted} {selected_time}:00"
        local_tz = pytz.timezone(DEFAULT_TIMEZONE)
        start_time = local_tz.localize(datetime.strptime(f"{date_container} {selected_time}", "%Y-%m-%d %H:%M"))
        end_time = start_time + timedelta(minutes=45)

        # Step 2: Perform the cancellation operation
        success = delete_internet_booking(
            start_time1=start_time1,
            mem_no=player_no,
            player_no_column=player_no_column
        )

        if not success:
            return jsonify({"error": "Failed to delete booking. No matching record found."}), 404

        # Step 3: Process waiting list notifications
        try:
            formatted_date = date_formatted
            print(f"[INFO] Triggering waiting list notifications for {formatted_date} at {selected_time}")
            process_waiting_list_notifications(formatted_date, selected_time)
        except Exception as e:
            print(f"[ERROR] Failed to process waiting list notifications: {e}")

        # Step 4: Call the financial update
        financial_result = delete_booking_financials(player_no, period_id)
        if financial_result["status"] == "error":
            return jsonify({
                "message": "Booking deleted, but financial update failed.",
                "error": financial_result["message"]
            }), 500

        # Step 5: Update session credit
        updated_credit = financial_result["financial_data"]["updated_credit"]
        session['credit'] = updated_credit

        return jsonify({
            "message": "Booking successfully deleted.",
            "financial_data": financial_result["financial_data"],
            "updated_credit": updated_credit
        }), 200
    except Exception as e:
        print(f"[ERROR] Exception in delete_booking: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            # Log the audit information
            log_audit_online_booking(
                mem_no=player_no if 'player_no' in locals() else None,
                court_date=start_time1 if 'start_time1' in locals() else datetime.now().strftime("%d/%m/%Y %H:%M"),
                court=selected_court if 'selected_court' in locals() else "Unknown",
                first_name=session.get('first_name', "Unknown"),
                last_name=session.get('last_name', "Unknown"),
                activity=101  # Hardcoded for cancellation
            )
        except Exception as e:
            print(f"[ERROR] Audit log failed: {e}")

def delete_booking_financials(player_no, period_id):
    """
    Perform the financial update for a successful cancellation.
    Updates the S_Credit in the database.

    Args:
        player_no (int): Member number of the player.
        period_id (int): Booking period identifier to select the correct cancellation fee.
    """
    try:
        from flask import current_app, request

        # Construct the financial data payload
        financial_payload = {"mem_no": player_no, "cost_type": "ICANCEL", "period_id": period_id}
        print(f"[DEBUG] Financial payload for cancellation: {financial_payload}")  # Log payload for debugging

        # Construct the financial endpoint dynamically
        financial_endpoint = f"{request.host_url}financials/calculated_internet_bookings".rstrip("/")
        print(f"[DEBUG] Financial endpoint URL: {financial_endpoint}")

        # Use current_app.test_client() to make the POST request
        with current_app.test_client() as client:
            financial_response = client.post(
                financial_endpoint,
                json=financial_payload,
                follow_redirects=True,
            )

        if financial_response.status_code == 200:
            financial_data = financial_response.get_json()
            updated_credit = financial_data.get("updated_credit")

            # Persist updated S_Credit to the database
            member_profile = get_squash_members_profile(username=player_no)
            if member_profile:
                update_success = update_squash_member_profile(
                    member_no=player_no,
                    first_name=member_profile["first_name"],
                    last_name=member_profile["surname"],
                    cell_phone=member_profile["cell_phone"],
                    email=member_profile["email"],
                    credit=updated_credit  # Update only S_Credit for the specific Mem_No
                )
                if not update_success:
                    return {
                        "status": "error",
                        "message": "Failed to update S_Credit in the database."
                    }

            return {
                "status": "success",
                "financial_data": financial_data
            }
        else:
            return {
                "status": "error",
                "message": f"Financial API failed for cancellation. Response: {financial_response.text}"
            }

    except Exception as e:
        print(f"[ERROR] Exception in delete_booking_financials: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# View weekly bookings viewbookings.html
@bookings_bp.route('/viewbookings/', methods=['GET'])
def view_bookings_page():
    """
    Render the View Bookings HTML template.
    """
    return render_template('viewbookings.html')

# View total bookings and cancellation.
@bookings_bp.route('/viewbookings', methods=['GET'])
def view_bookings():
    """
    Fetch and return weekly bookings for the logged-in member.
    """
    try:
        mem_no = session.get('Mem_No')
        if not mem_no:
            return jsonify({"error": "Unauthorized access. Please log in again."}), 401

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify({"error": "Missing required parameters: start_date or end_date."}), 400

        # Fetch the weekly bookings data
        bookings_data = get_booked_players_memno(start_date, end_date)
        print(f"[DEBUG] Bookings data fetched: {bookings_data}")

        # Fetch court descriptions
        courts_with_ids = get_courts_with_ids()
        print(f"[DEBUG] Court descriptions fetched: {courts_with_ids}")

        # Ensure bookings_data is converted to a list of dictionaries
        if isinstance(bookings_data, pd.DataFrame):
            bookings_data = bookings_data.to_dict(orient='records')

        # Ensure bookings_data is a list of dictionaries
        if not isinstance(bookings_data, list):
            print("[ERROR] Unexpected data format for bookings_data")
            return jsonify({"error": "Unexpected data format received from the database."}), 500

        # Format bookings for the logged-in member
        formatted_bookings = []
        for row in bookings_data:
            if isinstance(row, dict):
                player_numbers = [p.strip() for p in row.get("PlayerNos", "").split(",")]

                # Iterate over player_numbers to find the user's booking
                for court_index, player_no in enumerate(player_numbers):
                    if str(mem_no) == player_no:  # Match the current user
                        print(f"[DEBUG] Found booking for user {mem_no}: {row}")

                        # Extract court details based on court index
                        court_no = court_index + 1  # Court number is 1-based
                        start_time = row.get("StartTime", "N/A")
                        time_only = start_time.split(" ")[1][:5] if " " in start_time else None

                        # Derive date container and day of week
                        try:
                            date_obj = datetime.strptime(row["Date"], "%d/%m/%Y")
                            date_container = date_obj.strftime("%Y-%m-%d")
                        except (ValueError, TypeError):
                            print(f"[DEBUG] Invalid date format for booking: {row}")
                            continue

                        py_day = date_obj.weekday()  # 0=Mon
                        day_of_week = py_day + 2
                        if day_of_week == 8:
                            day_of_week = 1

                        # Determine slot ID based on time slot position
                        time_slots = get_time_slots(day_of_week)
                        if time_only in time_slots:
                            slot_id = time_slots.index(time_only) + 1
                            selected_time = time_slots[slot_id - 1]
                        else:
                            print(f"[DEBUG] Time {time_only} not found in time slots for day {day_of_week}")
                            continue

                        # Align court description if available
                        court_description = next(
                            (court["description"] for court in courts_with_ids if court["id"] == court_no), None
                        )

                        # Construct player_no_column dynamically
                        player_no_column = f"PlayerNo_{court_no}"

                        # Ensure all required fields are populated
                        if not (start_time and time_only and player_no_column and court_no):
                            print(f"[DEBUG] Missing data for booking: {row}")
                            continue  # Skip bookings with missing data

                        # Add formatted booking
                        formatted_bookings.append({
                            "date": row.get("Date", "N/A"),
                            "date_container": date_container,
                            "selected_time": selected_time,
                            "time": selected_time,
                            "slot_id": slot_id,
                            "status": "booked",
                            "action": "Cancel",
                            "court": court_no,
                            "court_description": court_description,
                            "player_no_column": player_no_column,
                            "player_no": mem_no,
                            "selected_court": court_no,
                        })

        print(f"[DEBUG] Formatted bookings: {formatted_bookings}")
        return jsonify({"status": "success", "bookings": formatted_bookings})

    except Exception as e:
        print(f"Error fetching bookings for member_no {session.get('Mem_No')}: {e}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500
