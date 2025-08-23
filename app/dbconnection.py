# DB connection to Court Manager Access database to retrieve and write various information.
import pyodbc
import pandas as pd
import threading
import time
from datetime import datetime

# Set Default time zone for correct database time retrieval.
DEFAULT_TIMEZONE = 'Africa/Windhoek'

# =======================================
# Enable ODBC Connection Pooling
# ---------------------------------------
# Connections are kept alive by pyODBC and reused across requests. They are
# explicitly closed when the Flask application shuts down.
pyodbc.pooling = True  # ✅ Enables built-in ODBC pooling

# =======================================
# Singleton Database Connection Manager
# =======================================


class _Singleton(type):
    """Thread-safe implementation of Singleton."""
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DatabaseConnectionManager(metaclass=_Singleton):
    """Provides singleton access to thread-local database connections."""

    def __init__(self):
        self._local = threading.local()

    def get_connection(self, dsn: str):
        conn = getattr(self._local, dsn, None)
        if conn is None or conn.closed:
            try:
                conn = pyodbc.connect(f"DSN={dsn}", autocommit=True)
                setattr(self._local, dsn, conn)
            except Exception as e:
                print(f"Database connection error ({dsn}): {e}")
                return None
        return conn

    def close_all(self):
        for name, conn in list(self._local.__dict__.items()):
            if conn is not None:
                try:
                    conn.close()
                finally:
                    setattr(self._local, name, None)

# =======================================
# Define ODBC DSN Names
# =======================================
odbc_courts = "CM_Courts"
odbc_status = "CM_Status"

# Define the ODBC connection strings using the DSN names
conn_str = f"DSN={odbc_courts}"
conn_str_status = f"DSN={odbc_status}"

# =======================================
# Function to Get Database Connections
# =======================================

_manager = DatabaseConnectionManager()


def get_db_connection():
    """Gets a thread-local database connection for CM_Courts."""
    return _manager.get_connection(odbc_courts)


def get_db_connection_status():
    """Gets a thread-local database connection for CM_Status."""
    return _manager.get_connection(odbc_status)


def close_db_connections():
    """Close any thread-local database connections.

    Called when the Flask application shuts down or at the end of a test
    request to release pooled connections.
    """
    _manager.close_all()

# =======================================
# Idle connection cleanup is handled automatically by ODBC pooling. Each worker
# thread manages its own connection, so no global cleanup thread is required.

# =======================================
# My profile and login details
# =======================================

# Function to get squash member profile details from the Clublist table
def get_squash_members_profile(username=None, start_mem_no=None, limit=50):
    """
    Retrieve a specific squash member's profile from the Clublist table if a username is provided,
    or retrieve a paginated list of profiles if no username is specified.
    Each entry includes surname, first name, member number, cell phone, email address,
    S_Code (used as a Pin/Password) with no decimals, S_Credit formatted to two decimal places,
    and Blocked status for reading only.

    Args:
        username (str, optional): The member number (username) to filter the query. Defaults to None.
        start_mem_no (int, optional): The starting [Mem_No] for pagination. Defaults to None.
        limit (int, optional): The maximum number of profiles to retrieve. Defaults to 50.

    Returns:
        dict or List[dict]: If username is provided, returns a dictionary with the relevant user's details.
                            If username is None, returns a list of member profiles.
    """
    members_profile = []

    try:
        conn = get_db_connection()  # Establish the database connection
        if not conn:
            return None if username else members_profile
        with conn.cursor() as cursor:
            
            if username:
                # Query to retrieve a specific profile for the given username
                query = """
                    SELECT [Surname], [First], [Mem_No], [CellPhone], [E_Mail_Adr], [S_Code], [S_Credit], [Blocked]
                    FROM [Clublist]
                    WHERE [Mem_No] = ?
                """
                cursor.execute(query, (username,))
                row = cursor.fetchone()
            
                if row:
                    # Return a single dictionary for the specified user
                    return {
                        "surname": row.Surname,
                        "first_name": row.First,
                        "member_no": int(row.Mem_No),  # Ensure Mem_No is treated as an integer
                        "cell_phone": row.CellPhone,
                        "email": row.E_Mail_Adr,
                        "pin": int(row.S_Code),  # Remove decimals by converting to an integer
                        "credit": f"{row.S_Credit if row.S_Credit is not None else 0:.2f}",  # Set None to 0.00
                        "blocked": row.Blocked  # Add Blocked column
                    }
                return None
            else:
                # Query to retrieve a paginated list of member profiles
                query = """
                    SELECT [Surname], [First], [Mem_No], [CellPhone], [E_Mail_Adr], [S_Code], [S_Credit], [Blocked]
                    FROM [Clublist]
                    WHERE [Mem_No] >= ?
                    ORDER BY [Mem_No]
                    FETCH FIRST ? ROWS ONLY
                """
                cursor.execute(query, (start_mem_no or 0, limit))  # Use 0 if start_mem_no is None
                rows = cursor.fetchall()

                for row in rows:
                    members_profile.append({
                        "surname": row.Surname,
                        "first_name": row.First,
                        "member_no": int(row.Mem_No),  # Ensure Mem_No is treated as an integer
                        "cell_phone": row.CellPhone,
                        "email": row.E_Mail_Adr,
                        "pin": int(row.S_Code),  # Remove decimals by converting to an integer
                        "credit": f"{row.S_Credit if row.S_Credit is not None else 0:.2f}",  # Set None to 0.00
                        "blocked": row.Blocked  # Add Blocked column
                    })
                return members_profile
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return None if username else members_profile


def get_member_profile_and_auth(username, password):
    """Retrieve a member's profile and validate credentials in a single query.

    Args:
        username (str): Member number.
        password (str): Membership password (S_Code).

    Returns:
        dict | None: Profile details if credentials are valid; otherwise ``None``.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
        with conn.cursor() as cursor:
            query = (
                "SELECT [Surname], [First], [Mem_No], [CellPhone], [E_Mail_Adr], [S_Credit], [Blocked] "
                "FROM [Clublist] WHERE [Mem_No] = ? AND [S_Code] = ?"
            )
            cursor.execute(query, (username, password))
            row = cursor.fetchone()
            if row:
                return {
                    "surname": row.Surname,
                    "first_name": row.First,
                    "member_no": int(row.Mem_No),
                    "cell_phone": row.CellPhone,
                    "email": row.E_Mail_Adr,
                    "credit": f"{row.S_Credit if row.S_Credit is not None else 0:.2f}",
                    "blocked": row.Blocked,
                }
            return None
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return None

# Only returns member number and email address
def get_member_email_and_memnumber(username=None, start_mem_no=None, limit=None):
    """
    Fetch member number and email based on criteria.
    Main purpose is for booking waiting list.

    Args:
        username (str, optional): Member number to filter the query. Defaults to None.
        start_mem_no (int, optional): Start member number for pagination. Defaults to None.
        limit (int, optional): Number of rows to fetch for pagination. Defaults to None.

    Returns:
        dict or list[dict]: Single dictionary for a specific user, or a list of dictionaries for pagination.
    """
    try:
        conn = get_db_connection()  # Establish the database connection
        if not conn:
            return None if username else []
        with conn.cursor() as cursor:
            
            if username:
                # Query for a specific user
                query = """
                    SELECT [Mem_No], [E_Mail_Adr]
                    FROM [Clublist]
                    WHERE [Mem_No] = ?
                """
                cursor.execute(query, (username,))
                row = cursor.fetchone()
            
                if row:
                    return {
                        "member_no": int(row.Mem_No),
                        "email": row.E_Mail_Adr
                    }
                return None
            else:
                # Query for paginated list
                query = """
                    SELECT [Mem_No], [E_Mail_Adr]
                    FROM [Clublist]
                    WHERE [Mem_No] >= ?
                    ORDER BY [Mem_No]
                    FETCH FIRST ? ROWS ONLY
                """
                cursor.execute(query, (start_mem_no or 0, limit))
                rows = cursor.fetchall()
            
                return [{
                    "member_no": int(row.Mem_No),
                    "email": row.E_Mail_Adr
                } for row in rows]
            
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return None if username else []


# Internet Type and Audit Log Details
def get_internet_types():
    """
    Retrieve all internet types from the InternetType table in the Status.mdb database.
    Each entry includes a code and its corresponding description.

    Returns:
        List[dict]: A list of dictionaries, each with 'code' and 'description' keys.
    """
    internet_types = []

    try:
        conn = get_db_connection_status()  # Connect to the Status.mdb database
        if not conn:
            return internet_types
        with conn.cursor() as cursor:
            query = "SELECT [Code], [Description] FROM [InternetType]"
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                internet_types.append({
                    "code": row.Code,
                    "description": row.Description
                })
            return internet_types
    except pyodbc.Error as e:
        print("Error accessing the InternetType table in the database:", e)
        return internet_types

# ======================================================
# Database Retrival Courts usage & time slots, Profile
# ======================================================

# Function to get court descriptions and their IDs, excluding descriptions containing 'Court'
def get_courts_with_ids():
    """
    Retrieve court descriptions, IDs, and numbers from the Courts table, excluding descriptions that contain 'Court'.
    Returns a list of dictionaries with 'id', 'number', and 'description' keys.
    """
    courts_with_ids = []
    try:
        conn = get_db_connection()
        if not conn:
            return courts_with_ids
        with conn.cursor() as cursor:
            query = "SELECT [Id], [CourtNo], [CourtDesc] FROM [Courts] WHERE [CourtDesc] NOT LIKE '%Court%'"
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                courts_with_ids.append({
                    "id": row.Id,
                    "number": row.CourtNo,
                    "description": row.CourtDesc.strip()
                })
            return courts_with_ids
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return courts_with_ids


# Function to get only court descriptions
def get_courts_descriptions():
    """
    Retrieve court descriptions from the Courts table, excluding descriptions that contain 'Court'.
    Returns a list of court descriptions as strings.
    """
    court_descriptions = []
    try:
        conn = get_db_connection()
        if not conn:
            return court_descriptions
        with conn.cursor() as cursor:
            query = "SELECT [CourtDesc] FROM [Courts] WHERE [CourtDesc] NOT LIKE '%Court%'"
            cursor.execute(query)
            rows = cursor.fetchall()
            court_descriptions = [row.CourtDesc for row in rows]
            return court_descriptions
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return court_descriptions


# Retrieve court descriptions from the Courts table, excluding descriptions that contain 'Court'.
# Explicitly associate each court with its corresponding PlayerNo column. Used for writing to DB for bookings
def get_courts_with_playerno():
    """
    Retrieve court descriptions from the Courts table, excluding descriptions that contain 'Court'.
    Explicitly associate each court with its corresponding PlayerNo column. Used for court bookings

    Returns:
        List[dict]: A list of dictionaries with court descriptions and their corresponding PlayerNo columns.
    """
    courts_with_playerno = []
    try:
        conn = get_db_connection()
        if not conn:
            return courts_with_playerno
        with conn.cursor() as cursor:
            query = "SELECT [Id], [CourtDesc] FROM [Courts] WHERE [CourtDesc] NOT LIKE '%Court%'"
            cursor.execute(query)
            rows = cursor.fetchall()
            for index, row in enumerate(rows):
                courts_with_playerno.append({
                    "description": row.CourtDesc,
                    "player_no_column": f"PlayerNo_{index + 1}"
                })
            return courts_with_playerno
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return courts_with_playerno


# Function to get time slots within a specified time range
def get_time_slots(day_of_week=None):
    """
    Retrieve unique time slots from the Booktime table, formatted as HH:MM.
    Sundays are limited until 19:00, while other days are up to 21:15.

    Args:
        day_of_week (int, optional): Day of the week (1 = Sunday, ..., 7 = Saturday).

    Returns:
        List[str]: A list of unique time slots as strings in HH:MM format.
    """
    time_slots = set()
    try:
        conn = get_db_connection()
        if not conn:
            return sorted(time_slots)
        with conn.cursor() as cursor:
            query = "SELECT DISTINCT StartTime1 FROM Booktime ORDER BY StartTime1"
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                start_time = row.StartTime1.strftime("%H:%M")
                if day_of_week == 1:
                    if "05:30" <= start_time <= "19:00":
                        time_slots.add(start_time)
                else:
                    if "05:30" <= start_time <= "21:15":
                        time_slots.add(start_time)
            return sorted(time_slots)
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return sorted(time_slots)


# =======================================
# Database Retrieval for Courts Periods
# =======================================
def get_court_periods_for_day(day_of_week):
    """
    Retrieve court periods for a specific day of the week from the Booktime table.
    Ensure each court is aligned with its respective Period ID.
    """
    court_periods = []
    try:
        conn = get_db_connection()
        if not conn:
            return court_periods
        with conn.cursor() as cursor:
            query = """
                SELECT [StartTime1], [CourtCode1], [CourtCode2], [CourtCode3], [CourtCode4]
                FROM [Booktime]
                WHERE [Day Of Week] = ?
                ORDER BY [StartTime1]
            """
            cursor.execute(query, (day_of_week,))
            rows = cursor.fetchall()
            
            period_mapping = {}
            period_query = "SELECT [ID], [DESCRIPT], [Color] FROM [Periods]"
            with conn.cursor() as period_cursor:
                period_cursor.execute(period_query)
                period_rows = period_cursor.fetchall()
                for period in period_rows:
                    period_mapping[period.ID] = {
                        "description": period.DESCRIPT,
                        "color": f"#{period.Color:06x}",
                        "period_id": period.ID
                    }

            for row in rows:
                court_periods.append({
                    "time": row.StartTime1.strftime("%H:%M"),
                    "court_1": period_mapping.get(row.CourtCode1, {"description": "Unknown", "color": "#FFFFFF", "period_id": None}),
                    "court_2": period_mapping.get(row.CourtCode2, {"description": "Unknown", "color": "#FFFFFF", "period_id": None}),
                    "court_3": period_mapping.get(row.CourtCode3, {"description": "Unknown", "color": "#FFFFFF", "period_id": None}),
                    "court_4": period_mapping.get(row.CourtCode4, {"description": "Unknown", "color": "#FFFFFF", "period_id": None}),
                })
            return court_periods
    except pyodbc.Error as e:
        print(f"Database error in get_court_periods_for_day: {e}")
        return court_periods


def get_period_ids_by_date_range(start_date, end_date):
    """
    Retrieve period IDs for a specific date range from the Bookfile table.

    Args:
        start_date (str): Start date in "dd/MM/yyyy" format.
        end_date (str): End date in "dd/MM/yyyy" format.

    Returns:
        List[dict]: A list of dictionaries with 'date', 'time', and 'periods' keys.
    """
    period_weekly_data = []
    try:
        print(f"[DEBUG] Retrieving periods for range: {start_date} to {end_date}")
        conn = get_db_connection()
        if not conn:
            return period_weekly_data
        with conn.cursor() as cursor:
            query = """
                SELECT [Date], [StartTime1], [BookCode1], [BookCode2], [BookCode3], [BookCode4],
                       [BookCode5], [BookCode6], [BookCode7], [BookCode8], [BookCode9], [BookCode10]
                FROM [Bookfile]
                WHERE [Date] BETWEEN ? AND ?
                ORDER BY [Date], [StartTime1]
            """
            cursor.execute(query, (start_date, end_date))
            rows = cursor.fetchall()

            for row in rows:
                if row.Date is not None and row.StartTime1 is not None:
                    periods = [
                        getattr(row, f"BookCode{i}")
                        for i in range(1, 11)
                        if getattr(row, f"BookCode{i}") is not None and getattr(row, f"BookCode{i}") != 0
                    ]
                    period_entry = {
                        "date": row.Date.strftime("%d/%m/%Y"),
                        "time": row.StartTime1.strftime("%H:%M"),
                        "periods": periods
                    }
                    period_weekly_data.append(period_entry)
                    print(f"[DEBUG] Period Entry: {period_entry}")
            return period_weekly_data
    except pyodbc.Error as e:
        print(f"[ERROR] Database error in get_period_ids_by_date_range: {e}")
        return period_weekly_data


def get_court_time_periods(conn=None):
    """
    Retrieve court periods aligned to court time slots from the Booktime table.
    Each time slot is associated with court period IDs (CourtCode1, CourtCode2, etc.).

    Args:
        conn (pyodbc.Connection, optional): Existing database connection. If ``None``,
            a new connection is obtained internally.

    Returns:
        List[dict]: A list of dictionaries, each with 'time' and 'court_periods' keys.
    """
    court_time_periods = []
    try:
        if conn is None:
            conn = get_db_connection()
        if not conn:
            return court_time_periods
        with conn.cursor() as cursor:
            query = """
                SELECT [StartTime1], [CourtCode1], [CourtCode2], [CourtCode3], [CourtCode4]
                FROM [Booktime]
                ORDER BY [StartTime1]
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                court_time_periods.append({
                    "time": row.StartTime1.strftime("%H:%M"),
                    "court_periods": {
                        "court_1": row.CourtCode1,
                        "court_2": row.CourtCode2,
                        "court_3": row.CourtCode3,
                        "court_4": row.CourtCode4,
                    }
                })
            return court_time_periods
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return court_time_periods

# =======================================
# Database Retrieval for Court Bookings
# =======================================

def get_bookings_with_periods(selected_date=None):
    """
    Retrieve court bookings with aligned periods for a specific date.
    Combines time slots, player bookings, and court periods.
    """
    if not selected_date:
        return []

    try:
        selected_day_of_week = (datetime.strptime(selected_date, "%d/%m/%Y").weekday() + 2) % 7 or 7
        bookings = get_booked_players(selected_date)
        periods = get_court_periods_for_day(selected_day_of_week)
        aligned_data = []
        time_slots = get_time_slots()

        for time_slot in time_slots:
            booking = next((b for b in bookings if b["time"] == time_slot), {"players": [None] * 10})
            period = next((p for p in periods if p["time"] == time_slot), {"court_periods": {}})
            aligned_data.append({
                "time": time_slot,
                "players": booking["players"],
                "court_periods": period["court_periods"],
            })

        return aligned_data

    except ValueError as ve:
        print(f"Error parsing selected date: {ve}")
        return []
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        return []


def get_periods():
    """
    Retrieve court periods from the Periods table.
    """
    periods = []
    try:
        conn = get_db_connection()
        if not conn:
            return periods
        with conn.cursor() as cursor:
            query = """
                SELECT [ID], [DESCRIPT], [Color]
                FROM [Periods]
                WHERE [DESCRIPT] IS NOT NULL AND [DESCRIPT] <> ''
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                periods.append({
                    "id": row.ID,
                    "description": row.DESCRIPT,
                    "color": row.Color
                })
            return periods
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return periods


def get_period_ids_by_day(day_of_week):
    """
    Retrieve period IDs for a specific day of the week from the Bookfile table.
    """
    period_data = []
    try:
        conn = get_db_connection()
        if not conn:
            return period_data
        with conn.cursor() as cursor:
            query = """
                SELECT [StartTime1], [BookCode1], [BookCode2], [BookCode3], [BookCode4]
                FROM [Bookfile]
                WHERE FORMAT([StartTime1], 'w') = ?
                ORDER BY [StartTime1]
            """
            cursor.execute(query, (day_of_week,))
            rows = cursor.fetchall()

            for row in rows:
                if row.StartTime1:
                    period_data.append({
                        "time": row.StartTime1.strftime("%H:%M"),
                        "periods": [row.BookCode1, row.BookCode2, row.BookCode3, row.BookCode4]
                    })
            return period_data
    except pyodbc.Error as e:
        print(f"Database error in get_period_ids_by_day: {e}")
        return period_data


def get_booked_players(selected_date=None, conn=None):
    """
    Retrieve player bookings for a specific date from the Bookfile table.

    Args:
        selected_date (str, optional): The date to fetch bookings for in ``dd/mm/yyyy`` format.
        conn (pyodbc.Connection, optional): Existing database connection. If ``None``, a
            new connection is obtained internally.
    """
    booked_players = []
    if not selected_date:
        return booked_players

    try:
        if conn is None:
            conn = get_db_connection()
        if not conn:
            return booked_players
        with conn.cursor() as cursor:
            query = """
                SELECT [Date], [StartTime1], [PlayName_1], [PlayName_2], [PlayName_3], [PlayName_4],
                       [PlayName_5], [PlayName_6], [PlayName_7], [PlayName_8], [PlayName_9], [PlayName_10]
                FROM [Bookfile]
                WHERE FORMAT([Date], 'dd/MM/yyyy') = ?
            """
            cursor.execute(query, (selected_date,))
            rows = cursor.fetchall()
            
            time_slots = get_time_slots()
            print("Time Slots:", time_slots)

            for row in rows:
                booking_time = row.StartTime1.strftime("%H:%M")
                nearest_slot = None
                slot_id = None
                for idx, slot in enumerate(time_slots, start=1):
                    if slot == booking_time:
                        nearest_slot = slot
                        slot_id = idx
                        break

                aligned_slot = nearest_slot or booking_time
                print(f"Booking Time: {booking_time}, Aligned Slot: {aligned_slot}")

                players = [row.PlayName_1, row.PlayName_2, row.PlayName_3, row.PlayName_4,
                           row.PlayName_5, row.PlayName_6, row.PlayName_7, row.PlayName_8,
                           row.PlayName_9, row.PlayName_10]
                cleaned_players = [p.strip() if p and "RESTRICTED" not in p.upper() else None for p in players]

                booked_players.append({
                    "date": row.Date.strftime("%d/%m/%Y"),
                    "time": aligned_slot,
                    "slot_id": slot_id,
                    "players": cleaned_players
                })
            return booked_players
    except (ValueError, pyodbc.Error) as e:
        print(f"Error retrieving bookings: {e}")
        return booked_players

# =======================================
# Database Retrieval for Booking costs
# =======================================

def get_court_rates_per_minute():
    """
    Retrieve rates per minute, booking counts, and cancellation counts for each court.
    """
    court_data = {}
    try:
        conn = get_db_connection()
        if not conn:
            return court_data
        with conn.cursor() as cursor:
            query = """
                SELECT [CourtDesc], [RATEPMIN1], [RATEPMIN2], [RATEPMIN3], [RATEPMIN4], [RATEPMIN5],
                       [IBOOKING1], [IBOOKING2], [IBOOKING3], [IBOOKING4], [IBOOKING5],
                       [ICANCEL1], [ICANCEL2], [ICANCEL3], [ICANCEL4], [ICANCEL5]
                FROM [Courts]
                WHERE [CourtDesc] NOT LIKE '%Court%'
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                rates = [row.RATEPMIN1, row.RATEPMIN2, row.RATEPMIN3, row.RATEPMIN4, row.RATEPMIN5]
                bookings = [row.IBOOKING1, row.IBOOKING2, row.IBOOKING3, row.IBOOKING4, row.IBOOKING5]
                cancellations = [row.ICANCEL1, row.ICANCEL2, row.ICANCEL3, row.ICANCEL4, row.ICANCEL5]

                valid_rates = [round(r, 4) for r in rates if r not in (0, None)]
                valid_bookings = [b for b in bookings if b not in (0, None)]
                valid_cancellations = [c for c in cancellations if c not in (0, None)]

                if valid_rates or valid_bookings or valid_cancellations:
                    court_data[row.CourtDesc] = {
                        "rates": valid_rates,
                        "bookings": valid_bookings,
                        "cancellations": valid_cancellations
                    }
            return court_data
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return court_data


def get_court_penalty_fees():
    """
    Retrieve penalty fees for unused bookings from the Courts table.
    """
    penalty_fees = {}
    try:
        conn = get_db_connection()
        if not conn:
            return penalty_fees
        with conn.cursor() as cursor:
            query = """
                SELECT [CourtDesc], [PENALTY1], [PENALTY2], [PENALTY3], [PENALTY4], [PENALTY5]
                FROM [Courts]
                WHERE [CourtDesc] NOT LIKE '%Court%'
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                penalties = [row.PENALTY1, row.PENALTY2, row.PENALTY3, row.PENALTY4, row.PENALTY5]
                valid_penalties = [round(p, 2) for p in penalties if p and p > 0]

                if valid_penalties:
                    penalty_fees[row.CourtDesc] = valid_penalties
            return penalty_fees
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return penalty_fees


def get_internet_booking_costs_and_cancellation_fees():
    """
    Retrieve internet booking costs and cancellation fees from the Courts table.
    """
    internet_data = {}
    try:
        conn = get_db_connection()
        if not conn:
            return internet_data
        with conn.cursor() as cursor:
            query = """
                SELECT [CourtDesc],
                       [IBOOKING1], [IBOOKING2], [IBOOKING3], [IBOOKING4], [IBOOKING5],
                       [ICANCEL1], [ICANCEL2], [ICANCEL3], [ICANCEL4], [ICANCEL5]
                FROM [Courts]
                WHERE [CourtDesc] NOT LIKE '%Court%'
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                booking_costs = [
                    getattr(row, f"IBOOKING{i}") for i in range(1, 6)
                    if getattr(row, f"IBOOKING{i}") and getattr(row, f"IBOOKING{i}") > 0
                ]
                cancellation_fees = [
                    getattr(row, f"ICANCEL{i}") for i in range(1, 6)
                    if getattr(row, f"ICANCEL{i}") and getattr(row, f"ICANCEL{i}") > 0
                ]

                if booking_costs or cancellation_fees:
                    internet_data[row.CourtDesc] = {
                        "booking_costs": [round(cost, 2) for cost in booking_costs],
                        "cancellation_fees": [round(fee, 2) for fee in cancellation_fees],
                    }
            return internet_data
    except pyodbc.Error as e:
        print("Error accessing the database:", e)
        return internet_data

# =======================================
# Booking Limitations retrieval
# =======================================
def get_booking_limitations(mem_no):
    """
    Retrieve booking limitations for a specific member from the Clublist table in the courts.mdb database.
    Exclude rows where any Book_ or Week_ columns have a value of 0.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
        with conn.cursor() as cursor:
            
            # Query to fetch the relevant columns for the specific Mem_No
            query = """
                SELECT [Mem_No], [Book_1], [Book_2], [Book_3], [Book_4], [Book_5],
                       [Week_1], [Week_2], [Week_3], [Week_4], [Week_5]
                FROM [Clublist]
                WHERE [Mem_No] = ?
            """
            cursor.execute(query, (mem_no,))
            row = cursor.fetchone()

            if row:
                # Process the row to filter out zero values
                daily_limits = [
                    getattr(row, f"Book_{i}") for i in range(1, 6)
                    if getattr(row, f"Book_{i}") and getattr(row, f"Book_{i}") > 0
                ]
                weekly_limits = [
                    getattr(row, f"Week_{i}") for i in range(1, 6)
                    if getattr(row, f"Week_{i}") and getattr(row, f"Week_{i}") > 0
                ]

                return {
                    "mem_no": row.Mem_No,
                    "daily_limits": daily_limits,
                    "weekly_limits": weekly_limits,
                }
            return None
    except pyodbc.Error as e:
        print(f"Error accessing the Clublist table in the database for Mem_No {mem_no}: {e}")
        return None


# Retrieving booked players specific for booking limitation process.
def get_booked_players_memno(start_date, end_date):
    """
    Fetch data from the Bookfile table within a specific date range and consolidate PlayerNo columns dynamically.
    The Date column is formatted as 'dd/MM/yyyy' and StartTime1 as 'dd/MM/yyyy HH:MM:SS'.
    """
    try:
        # Convert date format to dd/MM/yyyy (Access format)
        start_date = datetime.strptime(start_date, "%d/%m/%Y").strftime("%m/%d/%Y")
        end_date = datetime.strptime(end_date, "%d/%m/%Y").strftime("%m/%d/%Y")

        # Connect to the database using pyodbc
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
        with conn.cursor() as cursor:
            
            # SQL query to fetch data within the date range (MS Access syntax)
            query = f"""
                SELECT * FROM [Bookfile]
                WHERE [Date] BETWEEN #{start_date}# AND #{end_date}#
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Convert results into a pandas DataFrame
            data = pd.DataFrame.from_records(rows, columns=columns)
            
            # Debugging information: Print number of rows fetched
            print(f"[DEBUG] Number of rows fetched: {len(data)}")
            
            # Format Date and StartTime1 columns
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date']).dt.strftime("%d/%m/%Y")
            if 'StartTime1' in data.columns:
                data['StartTime1'] = pd.to_datetime(data['StartTime1']).dt.strftime("%d/%m/%Y %H:%M:%S")
            
            # Dynamically identify all columns with "PlayerNo"
            player_columns = [col for col in data.columns if "PlayerNo" in col]
            
            consolidated_data = []
            for _, row in data.iterrows():
                player_list = []
                for col in player_columns:
                    if row[col] == -9:
                        continue
                    elif pd.isna(row[col]):
                        player_list.append("None")
                    else:
                        player_list.append(int(row[col]))
            
                consolidated_row = {
                    'Date': row['Date'],
                    'StartTime': row['StartTime1'],
                    'PlayerNos': ", ".join(map(str, player_list)),
                }
                print(f"[DEBUG] Consolidated row: {consolidated_row}")
                consolidated_data.append(consolidated_row)
            
            return pd.DataFrame(consolidated_data)
            
    except pyodbc.Error as e:
        print(f"[ERROR] Failed to access the database in get_booked_players_memno: {e}")
        return pd.DataFrame()

# =======================================
# Database Write functions
# =======================================

def log_internet_login(mem_no, court_date, first_name, last_name, activity):
    """
    Logs internet login information into the Internetlog table.
    """
    try:
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        description = f"{first_name[0]} {last_name}"

        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            query = """
                INSERT INTO Internetlog ([Date], [Mem_No], [Court_Date], [Process_Date], [Description], [Activity])
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, current_time, mem_no, court_date, current_time, description, activity)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error inserting login information into the database:", e)
        return False


def ensure_login_internet_type():
    """
    Ensures InternetType table has Code=600 for login.
    """
    try:
        conn = get_db_connection_status()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            check_query = """
                SELECT COUNT(*) 
                FROM InternetType 
                WHERE [Code] = 600 AND [Description] = 'Internet login - Successful'
            """
            cursor.execute(check_query)
            if cursor.fetchone()[0] > 0:
                print("The login-related InternetType entry already exists.")
                return True
            
            insert_query = """
                INSERT INTO InternetType ([Code], [Description])
                VALUES (600, 'Internet login - Successful')
            """
            cursor.execute(insert_query)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error accessing or updating the InternetType table:", e)
        return False


def update_squash_member_profile(member_no, first_name, last_name, cell_phone, email, credit):
    """
    Update squash member's profile.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cursor:
            query = """
                UPDATE Clublist
                SET [First] = ?, [Surname] = ?, [CellPhone] = ?, [E_Mail_Adr] = ?, [S_Credit] = ?
                WHERE [Mem_No] = ?
            """
            cursor.execute(query, first_name, last_name, cell_phone, email, credit, member_no)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error updating the database:", e)
        return False


def ensure_profile_update_internet_type():
    """
    Ensures InternetType table has Code=700 for profile update.
    """
    try:
        conn = get_db_connection_status()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            check_query = """
                SELECT COUNT(*) 
                FROM InternetType 
                WHERE [Code] = 700 AND [Description] = 'User profile updated'
            """
            cursor.execute(check_query)
            if cursor.fetchone()[0] > 0:
                print("The profile update-related InternetType entry already exists.")
                return True
            
            insert_query = """
                INSERT INTO InternetType ([Code], [Description])
                VALUES (700, 'User profile updated')
            """
            cursor.execute(insert_query)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error accessing or updating the InternetType table:", e)
        return False


def get_booking_cell(start_time, player_no_col):
    """Return the current member number in a booking slot."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        with conn.cursor() as cursor:
            query = f"SELECT [{player_no_col}] FROM [Bookfile] WHERE [StartTime1] = ?"
            cursor.execute(query, start_time)
            row = cursor.fetchone()
            # Treat a value of 0 as equivalent to an empty slot
            if not row:
                return None
            return row[0] if row[0] != 0 else None
    except pyodbc.Error as e:
        print(f"Database error in get_booking_cell: {e}")
        return None


def update_internet_bookings(date_container, mem_no, selected_court, selected_time):
    """Update the ``Bookfile`` table for internet bookings atomically."""
    try:
        start_time_value = f"{date_container} {selected_time}:00"
        player_no_col = selected_court["player_no_column"]
        play_name_col = player_no_col.replace("PlayerNo", "PlayName")

        member_profile = get_squash_members_profile(username=mem_no)
        if not member_profile:
            print("Member profile not found.")
            return {"status": "error", "message": "member profile missing"}

        player_name = f"{member_profile['first_name'][0]} {member_profile['surname']}"

        print(f"[DEBUG] Booking cell: {player_no_col}, {play_name_col}, {start_time_value}")

        conn = get_db_connection()
        if not conn:
            return {"status": "error", "message": "connection failed"}
        with conn.cursor() as cursor:
            
            query = f"""
                UPDATE [Bookfile]
                SET [{player_no_col}] = ?, [{play_name_col}] = ?
                WHERE [StartTime1] = ? AND ([{player_no_col}] IS NULL OR [{player_no_col}] = -9 OR [{player_no_col}] = 0)
            """
            cursor.execute(query, mem_no, player_name, start_time_value)
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"[SUCCESS] Updated booking for {player_name} at {start_time_value}.")
                return {"status": "success"}
            else:
                print("[ERROR] Slot already booked or time slot not found.")
                return {"status": "already_booked"}
    except pyodbc.Error as e:
        print(f"[ERROR] Database update failed: {e}")
        return {"status": "error", "message": str(e)}


def delete_internet_booking(start_time1, mem_no, player_no_column):
    """
    Delete an internet booking from Bookfile.
    """
    try:
        play_name_column = player_no_column.replace("PlayerNo", "PlayName")

        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            query = f"""
                UPDATE [Bookfile]
                SET [{player_no_column}] = NULL, [{play_name_column}] = NULL
                WHERE [StartTime1] = ? AND [{player_no_column}] = ?
            """
            cursor.execute(query, start_time1, mem_no)
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"Deleted booking for player {mem_no} at {start_time1}.")
                return True
            else:
                print(f"No matching booking found for {mem_no} at {start_time1}.")
                return False
    except pyodbc.Error as e:
        print("Error deleting booking from database:", e)
        return False


def log_audit_online_booking(mem_no, court_date, court, first_name, last_name, activity):
    """
    Logs audit entry for an online booking.
    """
    try:
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        description = f"{first_name[0]} {last_name}"

        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            query = """
                INSERT INTO Internetlog ([Date], [Mem_No], [Court_Date], [Process_Date], [Court], [Description], [Activity])
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, current_time, mem_no, court_date, current_time, court, description, activity)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error inserting audit information:", e)
        return False


def log_waitinglist_update(mem_no, court_date, first_name, last_name, activity):
    """
    Logs an entry when a user is added to or removed from the waiting list.
    """
    try:
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        description = f"{first_name[0]} {last_name}"

        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            query = """
                INSERT INTO Internetlog ([Date], [Mem_No], [Court_Date], [Process_Date], [Description], [Activity])
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, current_time, mem_no, court_date, current_time, description, activity)
            conn.commit()
            return cursor.rowcount > 0
    except pyodbc.Error as e:
        print("Error inserting waiting list log entry:", e)
        return False


def ensure_waitinglist_internet_type():
    """
    Ensures that required InternetType codes for waiting list (650 and 651) exist.
    """
    try:
        conn = get_db_connection_status()
        if not conn:
            return False
        with conn.cursor() as cursor:
            
            entries = [
                (650, 'Waitinglist - Successfully added'),
                (651, 'Waitinglist - Error')
            ]
            all_success = True
            
            for code, description in entries:
                check_query = f"""
                    SELECT COUNT(*) 
                    FROM InternetType 
                    WHERE [Code] = {code} AND [Description] = '{description}'
                """
                cursor.execute(check_query)
                if cursor.fetchone()[0] == 0:
                    insert_query = f"""
                        INSERT INTO InternetType ([Code], [Description])
                        VALUES ({code}, '{description}')
                    """
                    cursor.execute(insert_query)
                    conn.commit()
                    if cursor.rowcount > 0:
                        print(f"Inserted InternetType entry {code}: {description}")
                    else:
                        print(f"Failed to insert entry {code}: {description}")
                        all_success = False
            return all_success
    except pyodbc.Error as e:
        print("Error updating InternetType table for waiting list:", e)
        return False

