# Run the Flask application by initializing it via the factory method
from app import create_app

# Create the Flask application using the factory pattern
app = create_app()

# Optional boot marker: log when run.py is loaded
try:
    import pathlib, datetime
    log_dir = pathlib.Path(r"C:\wanderers_web\AutoStart\logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wsgi_boot.txt"
    log_file.write_text(
        f"run.py loaded at {datetime.datetime.now()}\n",
        encoding="utf-8"
    )
except Exception:
    pass

if __name__ == '__main__':
    """
    Entry point for running the Flask application.
    Debug mode is enabled for development purposes.
    The application runs on port 5500 by default.
    """
    app.run(debug=True, host='0.0.0.0', port=8181)  # Adjust debug=False for production
