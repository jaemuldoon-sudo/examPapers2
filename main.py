"""
aimaths.ie — Streamlit app
-------------------------------------------------------------------------------
Features:
  - Passwordless login via Supabase email OTP (6-digit code)
  - One-time €50 paywall (checked via the check_paid RPC function)
  - Login logging (via the record_login RPC function)
  - 3-hour session expiry
  - Two-factor admin dashboard:
        * must be logged in as ADMIN_EMAIL, AND
        * must enter a fresh magic code sent (via Resend) to a SEPARATE
          admin-only email (ADMIN_NOTIFY_EMAIL)
    Admin table reads use the service_role key, which bypasses RLS — this key
    is ONLY ever used inside the admin block, which is gated as above.

-------------------------------------------------------------------------------
Environment variables (set on the Railway *Streamlit* service):
    SUPABASE_URL           https://kvvdimmkbwudeftsgagc.supabase.co
    SUPABASE_ANON_KEY      eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt2dmRpbW1rYnd1ZGVmdHNnYWdjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcyMTk3NjksImV4cCI6MjEwMjc5NTc2OX0.2VlgMJeILhxFX-AYU4XZqgDS-_VT_MCjfTCpmn8xnC8
    SUPABASE_SERVICE_KEY   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imt2dmRpbW1rYnd1ZGVmdHNnYWdjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIxOTc2OSwiZXhwIjoyMTAyNzk1NzY5fQ.M1cuIY0s8nEER5mv1VRKHRnhPB_2qXeLhPK7ay_G2Lo




    STRIPE_PAYMENT_LINK    https://buy.stripe.com/test_dRmeVdgag0Grfsi0qj3F602
       
    ADMIN_EMAIL            aimaths2026@gmail.com  (who may be admin)
    ADMIN_NOTIFY_EMAIL     jaemuldoon@gmail.com
      
    ADMIN_CODE_FROM        noreply@aimaths.ie

The Stripe webhook that flags users as paid runs as a SEPARATE service
(see webhook.py). This app only READS paid status.
-------------------------------------------------------------------------------
"""

import os
import random
from collections import Counter
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st
from supabase import create_client
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SESSION_HOURS = 3

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK")

ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
ADMIN_CODE_FROM = os.getenv("ADMIN_CODE_FROM", "noreply@aimaths.ie")

# normal app client (anon key - restricted by RLS)
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Helpers - normal app
# ---------------------------------------------------------------------------
def has_paid(email: str) -> bool:
    res = supabase.rpc("check_paid", {"user_email": email}).execute()
    return bool(res.data)


def log_login(email: str):
    supabase.rpc("record_login", {"user_email": email}).execute()


def logout(message=None):
    for key in ["email", "login_time", "code_sent", "pending_email",
                "admin_unlocked", "admin_code", "admin_code_sent"]:
        st.session_state.pop(key, None)
    if message:
        st.warning(message)


# ---------------------------------------------------------------------------
# Helpers - admin two-factor
# ---------------------------------------------------------------------------
def send_admin_code(code: str) -> bool:
    """Email a fresh admin unlock code to the separate admin address via Resend."""
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": f"aimaths.ie admin <{ADMIN_CODE_FROM}>",
                "to": [ADMIN_NOTIFY_EMAIL],
                "subject": "Your aimaths.ie admin unlock code",
                "html": (
                    "<p>Your admin unlock code is:</p>"
                    f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px;'>{code}</p>"
                    "<p>If you didn't request this, someone is trying to open the "
                    "admin panel. It cannot be opened without this code.</p>"
                ),
            },
            timeout=15,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def admin_service_client():
    """Service-role client - bypasses RLS. ONLY created inside the gated admin block."""
    return create_client(SUPABASE_URL, os.getenv("SUPABASE_SERVICE_KEY"))


# ---------------------------------------------------------------------------
# Session defaults
# ---------------------------------------------------------------------------
st.session_state.setdefault("email", None)
st.session_state.setdefault("code_sent", False)
st.session_state.setdefault("admin_unlocked", False)
st.session_state.setdefault("admin_code_sent", False)

# ---------------------------------------------------------------------------
# Session expiry
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
    st.title("One-time access - EUR 50")
    st.write("Get lifetime access to aimaths.ie.")
    pay_url = f"{STRIPE_PAYMENT_LINK}?prefilled_email={st.session_state.email}"
    st.link_button("Pay EUR 50 to unlock", pay_url)
    st.caption("After paying, come back here and click refresh.")
    if st.button("I've paid - refresh"):
        st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# PAID + LOGGED IN - your actual app
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
# ADMIN DASHBOARD  (two-factor: email identity + magic code to separate email)
# ---------------------------------------------------------------------------
if st.session_state.email == ADMIN_EMAIL:
    st.divider()
    st.subheader("Admin")

    if not st.session_state.admin_unlocked:
        # Factor 2: fresh code to the SEPARATE admin email
        if not st.session_state.admin_code_sent:
            if st.button("Unlock admin (send me a code)"):
                code = f"{random.randint(0, 999999):06d}"
                if send_admin_code(code):
                    st.session_state.admin_code = code
                    st.session_state.admin_code_sent = True
                    st.rerun()
                else:
                    st.error("Couldn't send the admin code. Check Resend settings.")
        else:
            st.info("An unlock code was sent to your admin email.")
            entered = st.text_input("Enter admin code", key="admin_code_entry")
            if st.button("Unlock"):
                if entered.strip() == st.session_state.get("admin_code"):
                    st.session_state.admin_unlocked = True
                    st.session_state.admin_code_sent = False
                    st.session_state.pop("admin_code", None)
                    st.rerun()
                else:
                    st.error("Incorrect code.")
            if st.button("Resend / start over"):
                st.session_state.admin_code_sent = False
                st.session_state.pop("admin_code", None)
                st.rerun()

    else:
        # UNLOCKED - service-role reads happen only here
        admin_db = admin_service_client()

        if st.button("Lock admin"):
            st.session_state.admin_unlocked = False
            st.rerun()

        st.markdown("#### Paid users")
        paid = admin_db.table("paid_users").select("*").order("paid_at", desc=True).execute()
        st.write(f"Total paid: {len(paid.data)}")
        st.dataframe(paid.data, use_container_width=True)

        st.markdown("#### Login activity")
        events = admin_db.table("login_events").select("*").execute().data
        if events:
            counts = Counter(e["email"] for e in events)
            last_seen = {}
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