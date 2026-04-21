import sys
import os

# Add the project root to sys.path so 'app' and 'ui' are importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Root entrypoint for Vercel to satisfy "No python entrypoint found"
# This file points to the main logic and UI entrypoints.

def app(environ, start_response):
    """
    A simple WSGI handler to satisfy Vercel's Python runtime.
    Note: The full Streamlit UI requires a persistent server and 
    may not run as a serverless function without advanced configuration.
    """
    status = '200 OK'
    headers = [('Content-type', 'text/plain; charset=utf-8')]
    start_response(status, headers)
    return [b"Bank Deposit Reconciliation System - Entrypoint Active"]

if __name__ == "__main__":
    # If run directly (e.g. locally), it will try to run the CLI logic
    from app.main import main
    main()
