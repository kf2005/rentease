"""WSGI entry point.

Production:  gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app
Development: python wsgi.py
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
