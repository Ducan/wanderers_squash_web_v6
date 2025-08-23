# Flask Blueprint for managing periods-related API endpoints
from flask import Blueprint, jsonify, request
from app.dbconnection import get_bookings_with_periods, get_periods
from datetime import datetime

# Define the blueprint
periods_bp = Blueprint('periods', __name__, url_prefix='/periods')

# =======================================
# Utility Functions
# =======================================

def convert_decimal_to_complementary_hex_color(decimal_color):
    """
    Convert a decimal color value to its complementary color in hex format.

    Args:
        decimal_color (int): The original color value in decimal format.

    Returns:
        str: The complementary color value in hex format (e.g., "#007FFF").
              If the input is invalid, defaults to "#000000" (black).
    """
    try:
        if decimal_color is None or not isinstance(decimal_color, int):
            return "#000000"  # Default to black if invalid input

        # Ensure the decimal value fits within the 24-bit RGB range
        if not (0 <= decimal_color <= 0xFFFFFF):
            return "#000000"  # Default to black for out-of-range inputs

        # Extract RGB components from the decimal value
        r = (decimal_color >> 16) & 0xFF  # Red component
        g = (decimal_color >> 8) & 0xFF   # Green component
        b = decimal_color & 0xFF          # Blue component

        # Calculate the complementary color
        comp_r = 255 - r
        comp_g = 255 - g
        comp_b = 255 - b

        # Format the complementary color as a hex string
        return f"#{comp_r:02X}{comp_g:02X}{comp_b:02X}"
    except Exception as e:
        print(f"Error: {e}")
        return "#000000"  # Default to black if any error occurs
    
def convert_decimal_to_hex_color(decimal_color):
    """
    Convert a decimal color value to its hex format.

    Args:
        decimal_color (int): The original color value in decimal format.

    Returns:
        str: The color value in hex format (e.g., "#007FFF").
              If the input is invalid, defaults to "#000000" (black).
    """
    try:
        if decimal_color is None or not isinstance(decimal_color, int):
            return "#000000"  # Default to black if invalid input

        # Ensure the decimal value fits within the 24-bit RGB range
        if not (0 <= decimal_color <= 0xFFFFFF):
            return "#000000"  # Default to black for out-of-range inputs

        # Format the color as a hex string
        return f"#{decimal_color:06X}"  # Convert to hex and pad with leading zeros if needed
    except Exception as e:
        print(f"Error: {e}")
        return "#000000"  # Default to black if any error occurs



# =======================================
# API Endpoints for Court Periods
# =======================================

@periods_bp.route('/get_periods_with_hex', methods=['GET'])
def get_periods_with_hex():
    """
    Retrieve court periods with color converted to hex format.

    Returns:
        JSON response with periods including hex color codes.
    """
    try:
        periods = get_periods()

        # Convert the color field to hex format
        for period in periods:
            period["color"] = convert_decimal_to_complementary_hex_color(period["color"])

        return jsonify({"status": "success", "data": periods}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve periods: {str(e)}"}), 500


@periods_bp.route('/courts/bookings_with_periods', methods=['GET'])
def get_bookings_with_periods_route():
    """
    Retrieve time slots, bookings, and periods for a specific date.

    Query Parameters:
        date (str): The date in "dd/MM/yyyy" format.

    Returns:
        JSON response with time slots, bookings, and periods.
    """
    selected_date = request.args.get('date')

    if not selected_date:
        return jsonify({"error": "Missing 'date' parameter. Provide in 'dd/MM/yyyy' format."}), 400

    try:
        # Ensure the date is valid and in the correct format
        datetime.strptime(selected_date, "%d/%m/%Y") 

        # Fetch combined data
        data = get_bookings_with_periods(selected_date)  
        return jsonify({"status": "success", "data": data}), 200
    except ValueError as ve:
        return jsonify({"error": f"Invalid date format: {str(ve)}"}), 400
    except Exception as e:
        print(f"Error fetching bookings with periods: {e}")
        return jsonify({"error": f"Failed to retrieve data: {str(e)}"}), 500


@periods_bp.route('/get_all_periods', methods=['GET'])
def get_all_periods():
    """
    Retrieve all available court periods with unique colors and descriptions.
    """
    try:
        periods = get_periods()  # Fetch all periods from the database
        for period in periods:
            period["color"] = f"#{period['color']:06X}"  # Convert decimal to hex
        return jsonify({"status": "success", "data": periods}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve all periods: {str(e)}"}), 500

