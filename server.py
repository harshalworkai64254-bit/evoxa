from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import json
import os
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# === ENVIRONMENT VARIABLES ===
client = OpenAI()  # Reads OPENAI_API_KEY automatically

USERS_FILE = "users.json"
USAGE_FILE = "usage.json"

ZOHO_SMTP_HOST = os.getenv("ZOHO_SMTP_HOST")
ZOHO_SMTP_PORT = 465
ZOHO_SENDER_EMAIL = os.getenv("ZOHO_SENDER_EMAIL")
ZOHO_SENDER_PASSWORD = os.getenv("ZOHO_SENDER_PASSWORD")
OWNER_EMAIL = "harshaladari@evoxa.co.uk"


def ensure_file(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)


ensure_file(USERS_FILE, {})
ensure_file(USAGE_FILE, {})


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def send_email_html(to_email, subject, html_body):
    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = ZOHO_SENDER_EMAIL
    msg["To"] = to_email

    smtp = smtplib.SMTP_SSL(ZOHO_SMTP_HOST, ZOHO_SMTP_PORT)
    smtp.login(ZOHO_SENDER_EMAIL, ZOHO_SENDER_PASSWORD)
    smtp.send_message(msg)
    smtp.quit()


@app.post("/signup")
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    users = load_json(USERS_FILE)
    if email in users:
        return jsonify({"error": "User already exists"}), 400

    users[email] = {
        "password": password,
        "verified": False
    }
    save_json(USERS_FILE, users)

    verification_link = f"https://evoxa.co.uk/verify?email={email}"

    html_body = f"""
    <html>
    <body>
        <h2>Verify your Evoxa account</h2>
        <p>Click below to verify your email:</p>
        <a href="{verification_link}">Verify Email</a>
    </body>
    </html>
    """

    try:
        send_email_html(email, "Verify your Evoxa account", html_body)
    except Exception as e:
        print("Verification email error:", e)

    return jsonify({"message": "Account created. Verification email sent."})


@app.get("/verify")
def verify():
    email = request.args.get("email")
    users = load_json(USERS_FILE)

    if email not in users:
        return "Invalid verification link."

    users[email]["verified"] = True
    save_json(USERS_FILE, users)

    return "Your email has been verified. You can now log in."


@app.post("/login")
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    users = load_json(USERS_FILE)
    user = users.get(email)

    if not user:
        return jsonify({"error": "Account not found"}), 404

    if user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401

    if not user["verified"]:
        return jsonify({"error": "Email not verified"}), 403

    return jsonify({"message": "Login successful"})


@app.post("/contact")
def contact():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    message = data.get("message")

    if not name or not email or not phone or not message:
        return jsonify({"error": "Missing fields"}), 400

    html_body = f"""
    <html>
    <body>
        <h2>New Contact Form Submission</h2>
        <p><strong>Name:</strong> {name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Phone:</strong> {phone}</p>
        <p><strong>Message:</strong> {message}</p>
    </body>
    </html>
    """

    try:
        send_email_html(OWNER_EMAIL, "New Evoxa Contact Form Submission", html_body)
        return jsonify({"message": "Email sent successfully"})
    except Exception as e:
        print("Contact email error:", e)
        return jsonify({"error": "Failed to send email"}), 500


@app.post("/chat")
def chat():
    data = request.json
    user_message = data.get("message", "")
    user_id = data.get("user_id", "anonymous")

    if not user_message:
        return jsonify({"reply": "I didn’t receive a message. Try again?"})

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "developer",
                "content": (
                    "You are Evoxa's AI customer service assistant. "
                    "You answer questions about Evoxa's services, pricing, websites, "
                    "AI live chat, and AI phone assistants. "
		    "Websites cost £75 for the first month then £25 a month. "
		    "AI Chatbots and AI Voice Receptionists require them to contact us and book an appointment. "
		    "A professional email costs £15 a month but must be bought along with the websites."
		    "See evoxa.co.uk for more info. Be clear and friendly"
                )
            },
            {"role": "user", "content": user_message}
        ]
    )

    reply = response.output_text
    tokens_used = response.usage.total_tokens

    usage = load_json(USAGE_FILE)
    if user_id not in usage:
        usage[user_id] = {"messages": 0, "tokens": 0}

    usage[user_id]["messages"] += 1
    usage[user_id]["tokens"] += tokens_used
    save_json(USAGE_FILE, usage)

    return jsonify({
        "reply": reply,
        "tokens_used": tokens_used
    })


@app.get("/usage")
def get_usage():
    usage = load_json(USAGE_FILE)
    return jsonify(usage)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)