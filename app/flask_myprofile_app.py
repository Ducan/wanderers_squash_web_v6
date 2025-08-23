from flask import Blueprint, render_template, session, jsonify, redirect, url_for, request
from datetime import datetime
from app.dbconnection import (
    get_squash_members_profile,
    update_squash_member_profile,
    ensure_profile_update_internet_type,
    log_internet_login,
)

# Create a blueprint for the My Profile functionality
myprofile_bp = Blueprint('myprofile', __name__)

@myprofile_bp.route('/', methods=['GET'])
def profile_page():
    """
    Renders the My Profile page if the user is logged in, displaying the user's first name and last name.
    Redirects the user to the login page if no valid session is found.
    """
    # Check if session contains first_name and last_name
    if 'first_name' in session and 'last_name' in session:
        return render_template(
            'myprofile.html',
            first_name=session.get('first_name'),
            last_name=session.get('last_name')
        )
    else:
        # Redirect to login if session data is missing
        return redirect(url_for('login.index'))

@myprofile_bp.route('/profile_data', methods=['GET'])
def profile_data():
    """
    API endpoint to fetch the logged-in user's complete profile data.
    """
    # Check if the user is logged in by verifying the session
    mem_no = session.get('Mem_No')
    if not mem_no:
        return jsonify({'error': 'Unauthorized access. Please log in again.'}), 401

    try:
        # Fetch the user's profile data from the database
        user_profile = get_squash_members_profile(username=mem_no)

        if user_profile:
            return jsonify(user_profile)
        else:
            # Return an error if the profile is not found
            return jsonify({'error': 'User profile not found.'}), 404
    except Exception as e:
        # Log the error for debugging purposes and return an internal server error
        print(f"Error fetching profile for member_no {mem_no}: {e}")
        return jsonify({'error': 'Internal server error. Please try again later.'}), 500

@myprofile_bp.route('/update_profile', methods=['POST'])
def update_profile():
    """
    API endpoint to update the logged-in user's profile.
    """
    mem_no = session.get('Mem_No')
    if not mem_no:
        return jsonify({'error': 'Unauthorized access. Please log in again.'}), 401

    try:
        # Retrieve updated profile data from the request
        data = request.json
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        cell_phone = data.get('cell_phone')
        email = data.get('email')
        credit = float(data.get('credit', 0))  # Ensure credit is converted to float

        # Call the update function
        success = update_squash_member_profile(
            member_no=mem_no,
            first_name=first_name,
            last_name=last_name,
            cell_phone=cell_phone,
            email=email,
            credit=credit
        )

        if success:
            # Ensure InternetType entry for profile update exists
            ensure_type_success = ensure_profile_update_internet_type()
            if not ensure_type_success:
                return jsonify({'error': 'Failed to ensure profile update type in the database.'}), 500

            # Log the profile update activity in InternetLog
            activity = 700
            log_success = log_internet_login(
                mem_no=int(mem_no),
                court_date=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),  # Use current time
                first_name=first_name,
                last_name=last_name,
                activity=activity
            )

            if not log_success:
                return jsonify({'error': 'Profile updated, but failed to log the activity.'}), 500

            # Refresh the session with updated profile information
            updated_profile = get_squash_members_profile(mem_no)
            if updated_profile:
                session['first_name'] = updated_profile.get('first_name')
                session['last_name'] = updated_profile.get('surname')
                session['credit'] = updated_profile.get('credit')
                session['cell_phone'] = updated_profile.get('cell_phone')
                session['email'] = updated_profile.get('email')

            return jsonify({'message': 'Profile updated successfully.'})
        else:
            return jsonify({'error': 'Failed to update profile. Please try again.'}), 400
    except Exception as e:
        print(f"Error updating profile for member_no {mem_no}: {e}")
        return jsonify({'error': 'Internal server error. Please try again later.'}), 500
