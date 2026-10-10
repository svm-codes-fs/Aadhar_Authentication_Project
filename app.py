"""
Entry point.

Development:   python app.py              then open http://127.0.0.1:5000
Production:    waitress-serve --port=8000 --call web:create_app
"""

from web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
