
import os
import requests
from urllib.parse import urlencode

from flask import Flask, render_template, redirect, session, url_for, jsonify
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from security import requires_permission
from flask_session import Session
from cachelib import SimpleCache
from datetime import timedelta

# Load credentials from .env
load_dotenv()

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

# Store sessions on the server rather than in browser cookies
app.config.update(
    SESSION_TYPE="cachelib",
    SESSION_CACHELIB=SimpleCache(),
    SESSION_PERMANENT=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30)
)

Session(app)

# Configure Auth0
oauth = OAuth(app)

oauth.register(
    name="auth0",
    client_id=os.environ["AUTH0_CLIENT_ID"],
    client_secret=os.environ["AUTH0_CLIENT_SECRET"],
    server_metadata_url=(
        f"https://{os.environ['AUTH0_DOMAIN']}"
        "/.well-known/openid-configuration"
    ),
    client_kwargs={
        "scope": (
            "openid profile email "
            "read:customer-data read:admin-data"
        )
    }
)

# Homepage
@app.route("/")
def home():
    return render_template("index.html", user=session.get("user"))

# Redirect user to Auth0 login

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True),
        audience=os.environ["AUTH0_AUDIENCE"]
    )


# Handle successful authentication

@app.route("/callback")
def callback():
    token = oauth.auth0.authorize_access_token()

    session.clear()

    # Save user profile and API token server-side
    session["user"] = dict(token["userinfo"])
    session["access_token"] = token["access_token"]

    return redirect(url_for("home"))


# Logout
@app.route("/logout")
def logout():
    session.clear()

    params = urlencode({
        "returnTo": url_for("home", _external=True),
        "client_id": os.environ["AUTH0_CLIENT_ID"]
    })

    return redirect(
        f"https://{os.environ['AUTH0_DOMAIN']}/v2/logout?{params}"
    )

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        user=session["user"]
    )


@app.route("/api/customer-data")
@requires_permission("read:customer-data")
def customer_data():

    return jsonify({
        "message": "Access granted",
        "resources": [
            "Account overview",
            "Support tickets",
            "Customer reports"
        ]
    }), 200


@app.route("/api/admin-data")
@requires_permission("read:admin-data")
def admin_data():

    return jsonify({
        "message": "Administrator access granted",
        "resources": [
            "User management",
            "Security reports",
            "System configuration"
        ]
    }), 200

@app.route("/demo/<resource>")
def demo_api(resource):

    # Require an authenticated browser session
    if "user" not in session:
        return redirect(url_for("login"))

    # Retrieve the token from the server-side session
    access_token = session.get("access_token")

    if not access_token:
        return jsonify({
            "error": "Please log in again"
        }), 401

    # Only allow these two predefined API endpoints
    endpoints = {
        "customer": "http://127.0.0.1:4040/api/customer-data",
        "admin": "http://127.0.0.1:4040/api/admin-data"
    }

    if resource not in endpoints:
        return jsonify({"error": "Not found"}), 404

    # Send the access token to the protected API
    try:
        response = requests.get(
            endpoints[resource],
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=5
        )

        return jsonify({
            "api": resource,
            "status_code": response.status_code,
            "result": response.json()
        }), response.status_code

    except requests.RequestException:
        return jsonify({
            "error": "API request failed"
        }), 502

# Start Flask development server
if __name__ == "__main__":
    app.run(debug=True, port=4040)

