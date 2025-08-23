from flask import Blueprint, session, render_template, redirect, url_for

faq_bp = Blueprint('faq', __name__)

@faq_bp.route('/', methods=['GET'])
def faq_page():
    """
    Renders the FAQ page if the user is logged in.
    Redirects the user to the login page if no valid session is found.
    """
    print("Session content:", session)  # Debugging
    if 'Mem_No' in session:
        return render_template('faq.html', user={
            "first_name": session.get("first_name"),
            "last_name": session.get("last_name"),
            "credit": session.get("credit")
        })
    else:
        print("No valid session. Redirecting to login.")  # Debugging
        return redirect(url_for('login.index'))

