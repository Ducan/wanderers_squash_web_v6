# Courts core data
from flask import (
    Blueprint,
    render_template,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    make_response,
)
from app.dbconnection import (
    get_time_slots,
    get_periods,
    get_court_time_periods,
    get_period_ids_by_day,
    get_court_periods_for_day,
    get_booked_players,
    get_courts_with_ids,
    get_db_connection,
)
from datetime import datetime

# Blueprint for the courts functionality
courts_bp = Blueprint('courts', __name__)


@courts_bp.after_request
def add_no_cache_headers(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Starting loading courts page
@courts_bp.route('/', methods=['GET'])
def courts_page():
    """
    Serve the courts.html page with user session details if logged in.
    Redirect to login if the user is not logged in.
    """
    if 'Mem_No' not in session or 'first_name' not in session or 'last_name' not in session:  # Check for valid session
        return redirect(url_for('login.index'))

    # Pass session details to the template
    user_info = {
        'first_name': session.get('first_name'),
        'last_name': session.get('last_name'),
        'credit': session.get('credit'),
    }
    response = make_response(render_template('courts.html', user=user_info))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Getting Court ID
@courts_bp.route('/descriptions', methods=['GET'])
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


@courts_bp.route('/get_user_info', methods=['GET'])
def get_user_info():
    """
    API endpoint to retrieve the first and last name of the logged-in user.
    """
    if 'Mem_No' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    return jsonify({
        'first_name': session.get('first_name'),
        'last_name': session.get('last_name')
    })

# Debug route to confirm session data
@courts_bp.route('/debug_session', methods=['GET'])
def debug_session():
    """
    Debug route to print the current session data.
    """
    return jsonify(dict(session)), 200

@courts_bp.route('/time_slots', methods=['GET'])
def get_time_slots_api():
    """
    API endpoint to retrieve time slots filtered for a specific day.
    """
    if 'Mem_No' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({"error": "No date provided"}), 400

    try:
        # Validate the date format
        date_obj = datetime.strptime(selected_date, "%d/%m/%Y")

        # Map day_of_week: 1 = Sunday, 2 = Monday, ..., 7 = Saturday
        day_of_week = (date_obj.weekday() + 2)
        if day_of_week == 8:
            day_of_week = 1

        # Fetch time slots already filtered for the day
        filtered_time_slots = get_time_slots(day_of_week)

        date_iso = date_obj.strftime("%Y-%m-%d")
        slots = [
            {
                "time": slot,
                "slot_id": idx,
                "slot_key": f"{date_iso} | slot #{idx}",
            }
            for idx, slot in enumerate(filtered_time_slots, start=1)
        ]

        return jsonify({"time_slots": slots})
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected format: dd/mm/yyyy."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from app.dbconnection import get_periods  # Import the function

# Getting periods data from Periods column
@courts_bp.route('/periods/get_all', methods=['GET'])
def get_all_periods():
    """
    API endpoint to fetch all court periods with their ID, description, and color.
    """
    try:
        periods = get_periods()
        return jsonify({"status": "success", "data": periods}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve periods: {str(e)}"}), 500

    
@courts_bp.route('/periods_for_day', methods=['GET'])
def get_periods_for_day():
    """
    API endpoint to fetch periods for a specific day.
    Dynamically align BookCode values to court descriptions based on the courts_container.
    """
    selected_date = request.args.get('date')
    if not selected_date:
        return jsonify({"error": "No date provided"}), 400

    try:
        # Validate the selected date format
        date_obj = datetime.strptime(selected_date, "%d/%m/%Y")

        # Map day_of_week: 1 = Sunday, 2 = Monday, ..., 7 = Saturday
        day_of_week = (date_obj.weekday() + 2) % 7 or 7

        # Fetch court descriptions (used for alignment)
        court_descriptions = get_courts_with_ids()  # [{id: 1, description: 'Court A', ...}, ...]

        # Fetch period descriptions for the day
        periods = get_court_periods_for_day(day_of_week)

        # Fetch period IDs from the database using Bookfile
        period_ids = get_period_ids_by_day(day_of_week)

        # Dynamically map period IDs to courts using court descriptions
        for period, period_id_row in zip(periods, period_ids):
            if period["time"] == period_id_row["time"]:
                for idx, court in enumerate(court_descriptions):
                    court_key = f"court_{idx + 1}"  # Dynamically generate court keys
                    if court_key in period and idx < len(period_id_row["periods"]):  # Ensure valid mapping
                        period[court_key]["period_id"] = period_id_row["periods"][idx]


        return jsonify(periods), 200
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected format: dd/mm/yyyy."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@courts_bp.route('/periods_usage', methods=['GET'])
def get_court_periods_usage():
    """
    API endpoint to fetch court usage and align it with periods data.
    Combines player names (from court bookings) with period colors.

    Returns:
        JSON: A list of dictionaries with 'time', 'court_id', 'player_name', and 'color'.
    """
    selected_date = request.args.get('date')  # Get the selected date from query params
    if not selected_date:
        return jsonify({"error": "No date provided"}), 400

    try:
        # Validate the selected date format
        datetime.strptime(selected_date, "%d/%m/%Y")

        # Fetch booked players and periods using a single shared connection
        conn = get_db_connection()
        bookings = get_booked_players(selected_date, conn)
        court_time_periods = get_court_time_periods(conn)

        # Define colors for periods
        period_colors = {
            1: "#ffffff",  # Normal
            2: "#ffcccb",  # Peak
            3: "#add8e6",  # Special
            None: "#f4f4f4"  # Default for N/A
        }

        # Merge bookings and periods data
        merged_data = []
        for booking in bookings:
            matching_period = next(
                (entry for entry in court_time_periods if entry['time'] == booking["time"]), None
            )
            for index, player_name in enumerate(booking["players"]):
                court_id = index + 1  # Align player index to court ID (1-based index)
                color = period_colors.get(
                    matching_period['court_periods'].get(f"court_{court_id}"),
                    "#f4f4f4"
                ) if matching_period else "#f4f4f4"

                merged_data.append({
                    "time": booking["time"],
                    "court_id": court_id,
                    "player_name": player_name,
                    "color": color
                })

        return jsonify(merged_data), 200

    except ValueError:
        return jsonify({"error": "Invalid date format. Expected format: dd/mm/yyyy."}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to fetch data: {str(e)}"}), 500

@courts_bp.route('/bookings', methods=['GET'])
def get_court_bookings():
    """
    API endpoint to fetch player bookings for a specific date.
    Returns the aligned time slots with players booked on that slot.
    """
    selected_date = request.args.get('date')  # Get the selected date from query params
    if not selected_date:
        return jsonify({"error": "No date provided"}), 400

    try:
        # Validate the selected date format
        datetime.strptime(selected_date, "%d/%m/%Y")

        # Fetch booked players for the given date
        bookings = get_booked_players(selected_date)

        return jsonify(bookings), 200

    except ValueError:
        return jsonify({"error": "Invalid date format. Expected format: dd/mm/yyyy."}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to fetch bookings: {str(e)}"}), 500