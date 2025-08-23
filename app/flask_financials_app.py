from flask import Blueprint, jsonify, request, session
from app.dbconnection import (
    get_squash_members_profile,
    update_squash_member_profile,
    get_court_rates_per_minute,
    get_periods
)

# Define the blueprint
financials_bp = Blueprint('financials', __name__, url_prefix='/financials')

@financials_bp.route('/calculated_internet_bookings', methods=['POST', 'GET'])
def calculated_internet_bookings():
    """
    Deduct or add IBOOKING/ICANCEL cost and update the user's S_Credit.
    Supports GET for simulation and POST for actual processing.
    """
    try:
        # Unified input retrieval
        mem_no = request.args.get('mem_no') if request.method == 'GET' else request.json.get('mem_no')
        cost_type = request.args.get('cost_type') if request.method == 'GET' else request.json.get('cost_type')

        # Validate inputs
        if not mem_no or cost_type not in ['IBOOKING', 'ICANCEL']:
            return jsonify({"error": "Invalid input data."}), 400

        # Fetch the member's profile
        member_profile = get_squash_members_profile(username=mem_no)
        if not member_profile:
            return jsonify({"error": "Member profile not found."}), 404

        current_credit = float(member_profile['credit'])

        # Fetch the cost based on cost_type
        court_data = get_court_rates_per_minute()
        cost = None
        for _, cost_data in court_data.items():
            if cost_type == 'IBOOKING':
                cost = cost_data.get('bookings', [None])[0]
            elif cost_type == 'ICANCEL':
                cost = cost_data.get('cancellations', [None])[0]
            if cost is not None:
                break

        if cost is None:
            return jsonify({"error": f"Cost for {cost_type} not found."}), 404

        # Explicitly handle IBOOKING and ICANCEL for updated_credit
        if cost_type == 'IBOOKING':
            updated_credit = current_credit - cost
        elif cost_type == 'ICANCEL':
            updated_credit = current_credit - cost
        else:
            return jsonify({"error": f"Unsupported cost type: {cost_type}"}), 400

        if request.method == 'POST':
            # Update S_Credit in the database
            success = update_squash_member_profile(
                member_no=mem_no,
                first_name=member_profile['first_name'],
                last_name=member_profile['surname'],
                cell_phone=member_profile['cell_phone'],
                email=member_profile['email'],
                credit=updated_credit
            )
            if not success:
                return jsonify({"error": "Failed to update credit."}), 500

        # Return the response
        return jsonify({
            "status": "success",
            "cost_type": cost_type,
            "cost": f"{cost:.2f}",
            "current_credit": f"{current_credit:.2f}",
            "updated_credit": f"{updated_credit:.2f}"
        }), 200

    except Exception as e:
        print(f"[ERROR] Exception in calculated_internet_bookings: {e}")
        return jsonify({"error": str(e)}), 500


@financials_bp.route('/court_booking_costs', methods=['GET'])
def get_court_booking_costs():
    """
    Calculate the total cost for a 45-minute court booking for each period type.
    """
    try:
        # Retrieve rates per minute and period descriptions
        court_rates = get_court_rates_per_minute()  # {'VISIONS': {'rates': [0.4444, 0.5555, ...]}, ...}
        periods = get_periods()  # [{'id': 1, 'description': 'NORMAL', ...}, ...]

        print("[DEBUG] Court Rates:", court_rates)  # Debug: Print court rates
        print("[DEBUG] Periods Data:", periods)    # Debug: Print periods data

        if not court_rates or not periods:
            print("[DEBUG] Missing data: Court rates or periods data is empty.")
            return jsonify({
                "status": "error",
                "message": "No court rates or periods data available",
                "data": []
            }), 404

        # Extract the rates (assuming all courts use the same rates)
        first_court = next(iter(court_rates.values()))  # Get the first court's rates
        rates = first_court.get("rates", [])

        print("[DEBUG] Rates Used for Calculations:", rates)  # Debug

        # Align rates with period IDs
        costs = []
        for period in periods:
            period_id = period.get('id')
            description = period.get('description')

            # Map period ID to the rates list index
            rate_index = period_id - 1  # Assuming IDs are 1-based and map directly to rates
            rate_per_min = rates[rate_index] if rate_index < len(rates) else None

            print(f"[DEBUG] Processing Period ID: {period_id}, Description: {description}, Rate Index: {rate_index}, Rate Per Minute: {rate_per_min}")  # Debug

            if rate_per_min is not None:
                # Calculate the total cost for 45 minutes and round it
                total_cost = round(rate_per_min * 45)
                print(f"[DEBUG] Calculated Total Cost for Period '{description}': {total_cost}")  # Debug
                costs.append({
                    "description": description,
                    "total_cost": f"{total_cost:.2f}"
                })
            else:
                # Handle cases where no rate exists for a period
                print(f"[DEBUG] No rate found for Period '{description}'. Setting Total Cost to 'N/A'.")  # Debug
                costs.append({
                    "description": description,
                    "total_cost": "N/A"
                })

        return jsonify({"status": "success", "data": costs}), 200

    except Exception as e:
        print(f"[ERROR] Exception in get_court_booking_costs: {e}")
        return jsonify({"error": str(e)}), 500



