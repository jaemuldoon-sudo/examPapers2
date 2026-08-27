"""
aimaths.ie — Streamlit app
Login (email OTP) + one-time €50 paywall + login logging + 3h session expiry + admin page.

Environment variables required (set these on the Railway Streamlit service):
    SUPABASE_URL          - your Supabase project URL
    SUPABASE_ANON_KEY     - Supabase anon/public key
    STRIPE_SECRET_KEY     - Stripe secret key (sk_test_... while testing)
    STRIPE_PAYMENT_LINK   - your €50 one-time Stripe Payment Link URL
    OPENAI_API_KEY        - your OpenAI key
    ADMIN_EMAILS          - comma-separated admin emails, e.g. you@aimaths.ie

The Stripe webhook that flags users as paid runs as a SEPARATE service
(see webhook.py). This app only READS the paid_users table.
"""

import os
from collections import Counter
from datetime import datetime, timezone, timedelta

import streamlit as st
from supabase import create_client
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SESSION_HOURS = 3  # how long a login stays valid

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def has_paid(email: str) -> bool:
    res = supabase.table("paid_users").select("email").eq("email", email).execute()
    return len(res.data) > 0


def log_login(email: str):
    supabase.table("login_events").insert({"email": email}).execute()


def logout(message: str | None = None):
    for key in ["email", "login_time", "code_sent", "pending_email"]:
        st.session_state.pop(key, None)
    if message:
        st.warning(message)


# ---------------------------------------------------------------------------
# Session defaults
# ---------------------------------------------------------------------------
if "email" not in st.session_state:
    st.session_state.email = None
if "code_sent" not in st.session_state:
    st.session_state.code_sent = False

# ---------------------------------------------------------------------------
# Session expiry check (runs every rerun)
# ---------------------------------------------------------------------------
if st.session_state.email is not None:
    login_time = st.session_state.get("login_time")
    if login_time is None or datetime.now(timezone.utc) - login_time > timedelta(hours=SESSION_HOURS):
        logout("Your session has expired. Please log in again.")
        st.rerun()

# ---------------------------------------------------------------------------
# LOGIN GATE
# ---------------------------------------------------------------------------
if st.session_state.email is None:
    st.title("Log in to aimaths.ie")

    if not st.session_state.code_sent:
        email_input = st.text_input("Your email address")
        if st.button("Send me a login code"):
            if email_input:
                clean = email_input.strip().lower()
                supabase.auth.sign_in_with_otp({"email": clean})
                st.session_state.pending_email = clean
                st.session_state.code_sent = True
                st.rerun()
            else:
                st.error("Please enter your email.")
    else:
        st.info(f"We emailed a 6-digit code to {st.session_state.pending_email}")
        code = st.text_input("Enter the code")
        if st.button("Verify"):
            try:
                supabase.auth.verify_otp({
                    "email": st.session_state.pending_email,
                    "token": code.strip(),
                    "type": "email",
                })
                st.session_state.email = st.session_state.pending_email
                st.session_state.code_sent = False
                st.session_state.login_time = datetime.now(timezone.utc)
                log_login(st.session_state.email)
                st.rerun()
            except Exception:
                st.error("Invalid or expired code. Try again.")
        if st.button("Use a different email"):
            st.session_state.code_sent = False
            st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# PAYWALL GATE
# ---------------------------------------------------------------------------
if not has_paid(st.session_state.email):
    st.title("One-time access — €50")
    st.write("Get lifetime access to aimaths.ie.")
    pay_url = f"{STRIPE_PAYMENT_LINK}?prefilled_email={st.session_state.email}"
    st.link_button("Pay €50 to unlock", pay_url)
    st.caption("After paying, come back here and click refresh.")
    if st.button("I've paid — refresh"):
        st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# PAID + LOGGED IN — your actual app
# ---------------------------------------------------------------------------
col1, col2 = st.columns([4, 1])
with col1:
    st.title("Welcome to aimaths.ie")
    st.caption(f"Logged in as {st.session_state.email}")
with col2:
    if st.button("Log out"):
        logout()
        st.rerun()

# ===========================================================================
# >>> YOUR EXISTING APP CODE GOES HERE <<<
# e.g. your OpenAI-powered maths features using `client`
# ===========================================================================
st.write("Your app content goes here.")


# ---------------------------------------------------------------------------
# ADMIN DASHBOARD (only visible to ADMIN_EMAILS)
# ---------------------------------------------------------------------------
if st.session_state.email in ADMIN_EMAILS:
    with st.expander("🔒 Admin dashboard"):
        st.subheader("Paid users")
        paid = supabase.table("paid_users").select("*").order("paid_at", desc=True).execute()
        st.write(f"Total paid: {len(paid.data)}")
        st.dataframe(paid.data, use_container_width=True)

        st.subheader("Login activity")
        events = supabase.table("login_events").select("*").execute().data
        if events:
            counts = Counter(e["email"] for e in events)
            last_seen: dict[str, str] = {}
            for e in events:
                ts = e["logged_in_at"]
                if e["email"] not in last_seen or ts > last_seen[e["email"]]:
                    last_seen[e["email"]] = ts
            summary = [
                {"email": em, "logins": c, "last_seen": last_seen[em]}
                for em, c in counts.most_common()
            ]
            st.dataframe(summary, use_container_width=True)
            st.metric("Total logins (all time)", len(events))
        else:
            st.write("No logins recorded yet.")