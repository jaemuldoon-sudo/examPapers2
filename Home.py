import streamlit as st
import re
import os
import json
from anthropic import Anthropic
import random
from datetime import datetime, timezone, timedelta
import requests
import html
import time
from supabase import create_client

#PAGE CONFIG (MUST BE FIRST ST COMMAND)
st.set_page_config(page_title="Leaving Certificate Honours Maths", layout="centered")



# ===========================================================================
# LOGIN + PAYWALL GATE
# Paste this block immediately AFTER st.set_page_config(...) and BEFORE the
# rest of your app. Nothing below this block runs until the user is logged in
# AND has paid. Works the same in all four apps (LCH/LCO/JCH/JCO).
#
# Required imports (add near the top of the file with your other imports):
#     import random
#     from datetime import datetime, timezone, timedelta
#     import requests
#     from supabase import create_client
#
# Required environment variables on this app's Railway service:
#     SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY,
#     STRIPE_PAYMENT_LINK, ADMIN_EMAIL, ADMIN_NOTIFY_EMAIL,
#     RESEND_API_KEY, ADMIN_CODE_FROM
# ===========================================================================

_SESSION_HOURS = 3

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
_STRIPE_PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK")
_ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
_ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL")
_RESEND_API_KEY = os.getenv("RESEND_API_KEY")
_ADMIN_CODE_FROM = os.getenv("ADMIN_CODE_FROM", "noreply@aimaths.ie")

_auth_supabase = create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)


def _has_paid(email):
    res = _auth_supabase.rpc("check_paid", {"user_email": email}).execute()
    return bool(res.data)


def _log_login(email):
    _auth_supabase.rpc("record_login", {"user_email": email}).execute()


def _auth_logout(message=None):
    for k in ["email", "login_time", "code_sent", "pending_email",
              "admin_unlocked", "admin_code", "admin_code_sent"]:
        st.session_state.pop(k, None)
    if message:
        st.warning(message)


def _send_admin_code(code):
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {_RESEND_API_KEY}"},
            json={
                "from": f"aimaths.ie admin <{_ADMIN_CODE_FROM}>",
                "to": [_ADMIN_NOTIFY_EMAIL],
                "subject": "Your aimaths.ie admin unlock code",
                "html": ("<p>Your admin unlock code is:</p>"
                         f"<p style='font-size:28px;font-weight:bold;letter-spacing:4px;'>{code}</p>"
                         "<p>If you didn't request this, someone is trying to open the admin panel.</p>"),
            },
            timeout=15,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


_APP_URL = os.getenv("APP_URL", "https://aimaths.ie")
_WORKSHEET_FROM = os.getenv("WORKSHEET_FROM", _ADMIN_CODE_FROM)


def _worksheet_link(ws_id):
    """Direct link to one shared worksheet, e.g. https://aimaths.ie/?worksheet=12"""
    return f"{_APP_URL.rstrip('/')}/?worksheet={ws_id}"


def _send_worksheet_emails(recipients, title, link=None):
    """Email each student individually (nobody sees anyone else's address).
    Uses Resend's batch endpoint: up to 100 emails per request.
    Returns (number sent, list of failed addresses)."""
    safe_title = html.escape(title)
    link = link or _APP_URL
    body = (
        "<p>Hi,</p>"
        f"<p>A new worksheet is ready for you on aimaths.ie: <b>{safe_title}</b></p>"
        f"<p><a href='{html.escape(link)}' style='display:inline-block;padding:12px 20px;"
        "background:#2b59c3;color:#fff;border-radius:8px;text-decoration:none;'>"
        "Open the worksheet</a></p>"
        "<p>You may need to log in first. The worksheet then opens at the top of the page, "
        "and each question has a worked solution.</p>"
        "<p style='color:#888;font-size:12px;'>You're getting this because you have an "
        "aimaths.ie account. To stop these emails, just reply 'unsubscribe'.</p>"
    )
    sent, failed = 0, []
    for i in range(0, len(recipients), 100):
        chunk = recipients[i:i + 100]
        payload = []
        for r in chunk:
            msg = {
                "from": f"aimaths.ie <{_WORKSHEET_FROM}>",
                "to": [r],
                "subject": f"New worksheet: {title}",
                "html": body,
            }
            if _ADMIN_NOTIFY_EMAIL:
                msg["reply_to"] = _ADMIN_NOTIFY_EMAIL
            payload.append(msg)
        try:
            resp = requests.post(
                "https://api.resend.com/emails/batch",
                headers={"Authorization": f"Bearer {_RESEND_API_KEY}"},
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                sent += len(chunk)
            else:
                failed += chunk
        except Exception:
            failed += chunk
        time.sleep(0.6)  # stay under Resend's rate limit
    return sent, failed


st.session_state.setdefault("email", None)
st.session_state.setdefault("code_sent", False)

# session expiry
if st.session_state.email is not None:
    _lt = st.session_state.get("login_time")
    if _lt is None or datetime.now(timezone.utc) - _lt > timedelta(hours=_SESSION_HOURS):
        _auth_logout("Your session has expired. Please log in again.")
        st.rerun()

# ---------------------------------------------------------------------------
# LOGIN GATE  (mobile-friendly, larger inputs & buttons)
# Replaces the LOGIN GATE section of your gate block.
# ---------------------------------------------------------------------------
if st.session_state.email is None:

    # --- mobile-friendly styling for the login screen ---
    st.markdown("""
        <style>
        /* bigger heading */
        .login-title {
            font-size: 2rem;
            font-weight: 700;
            text-align: center;
            margin: 1.2rem 0 0.4rem 0;
        }
        .login-sub {
            font-size: 1.1rem;
            text-align: center;
            color: #555;
            margin-bottom: 1.5rem;
        }
        /* enlarge text inputs */
        div[data-testid="stTextInput"] input {
            font-size: 1.25rem !important;
            padding: 0.9rem 1rem !important;
            height: auto !important;
        }
        /* enlarge input labels */
        div[data-testid="stTextInput"] label p {
            font-size: 1.1rem !important;
        }
        /* enlarge buttons and make them full width & tappable */
        div[data-testid="stButton"] button {
            font-size: 1.2rem !important;
            padding: 0.9rem 1rem !important;
            width: 100% !important;
            border-radius: 10px !important;
        }
        /* constrain width on desktop, full on mobile */
        .block-container {
            max-width: 480px;
            padding-top: 1rem;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-title">Log in to aimaths.ie</div>', unsafe_allow_html=True)

    if not st.session_state.code_sent:
        st.markdown('<div class="login-sub">Enter your email to get a login code</div>', unsafe_allow_html=True)
        _email_input = st.text_input("Email address")
        if st.button("Send me a login code"):
            if _email_input:
                _clean = _email_input.strip().lower()
                # Always advance to the code-entry screen. The code often sends
                # even when the client reports a transient error, so we move on
                # regardless and let the user type whatever code they receive.
                st.session_state.pending_email = _clean
                st.session_state.code_sent = True
                try:
                    _auth_supabase.auth.sign_in_with_otp({"email": _clean})
                except Exception as e:
                    msg = str(e).lower()
                    if "429" in msg or "rate" in msg or "too many" in msg:
                        st.session_state.login_notice = "Note: if you've requested several codes, use the most recent one, or wait a minute before requesting another."
                    else:
                        st.session_state.login_notice = ""
                st.rerun()
            else:
                st.error("Please enter your email.")
    else:
        st.markdown(
            f'<div class="login-sub">We emailed a 6-digit code to<br><b>{st.session_state.pending_email}</b></div>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("login_notice"):
            st.info(st.session_state.login_notice)
        _code = st.text_input("Enter the 6-digit code")
        if st.button("Verify"):
            try:
                _auth_supabase.auth.verify_otp({
                    "email": st.session_state.pending_email,
                    "token": _code.strip(),
                    "type": "email",
                })
                st.session_state.email = st.session_state.pending_email
                st.session_state.code_sent = False
                st.session_state.login_time = datetime.now(timezone.utc)
                _log_login(st.session_state.email)
                st.rerun()
            except Exception:
                st.error("Invalid or expired code. Try again.")
        if st.button("Use a different email"):
            st.session_state.code_sent = False
            st.rerun()
    st.stop()

# PAYWALL GATE
if not _has_paid(st.session_state.email):
    st.title("One-time access - EUR 49")
    st.write("Get lifetime access to all of aimaths.ie (all four levels).")
    _pay_url = f"{_STRIPE_PAYMENT_LINK}?prefilled_email={st.session_state.email}"
    st.link_button("Pay EUR 49 to unlock", _pay_url)
    st.caption("After paying, come back here and click refresh.")
    if st.button("I've paid - refresh"):
        st.rerun()
    st.stop()

# small logged-in bar
_c1, _c2 = st.columns([4, 1])
with _c2:
    if st.button("Log out"):
        _auth_logout()
        st.rerun()
# ===========================================================================
# END GATE — your normal app runs below, only for logged-in + paid users
# ===========================================================================









#st.write("API Key exists:", "ANTHROPIC_API_KEY" in os.environ)
#st.write("API Key value:", os.environ.get("ANTHROPIC_API_KEY", "NOT FOUND")[:20] + "...")
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# -----------------------------
# LOAD EXAM INDEX
# -----------------------------
# Load the exam index from file
#def load_exam_index():
#    """Load the exam index JSON file"""
#    try:
#        with open('exam-index.json', 'r') as f:
#            return json.load(f)
#    except FileNotFoundError:
#        st.warning("⚠️ exam-index.json not found. Upload it to your Railway deployment.")
#        return None


def load_all_exam_indexes():
    files = [
        'JSON Files/exam-index1.json',
        'JSON Files/exam-index2.json',
        'JSON Files/exam-index3.json',
        'JSON Files/exam-index4.json',
        'JSON Files/exam-index5.json',
        'JSON Files/exam-index6.json',
    ]
    all_questions = []
    all_topics = set()

    for filename in files:
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                all_questions.extend(data['questions'])
                all_topics.update(data['topics'])
        except FileNotFoundError:
            st.warning(f"⚠️ {filename} not found.")

    return {
        "total_questions": len(all_questions),
        "topics": sorted(list(all_topics)),
        "questions": all_questions
    }


EXAM_INDEX = load_all_exam_indexes()

# -----------------------------
# TOPICS + SUBTOPICS
# -----------------------------
TOPICS = ["Probability", "Trigonometry", "Algebra", "Geometry of the Circle", "Geometry of the Line", "Statistics", "Enlargements", "Integration", "Differentation", "Complex Numbers"]

SUBTOPICS = {
    "Probability": [
        "Combined events",
        "Conditional probability",
        "Expected value",
        "Venn Diagrams",
        "Permutations and combinations",
        "Binomial distribution",
        "Bernoulli Trials",
        "Normal Distribution"
    ],
    "Trigonometry": [
        "Trigonometric identities",
        "Graphs",
        "Radians",
        "Sine rule / Cosine rule",
        "Unit Circle",
        "Pytharagos Theorem",
        "Angles of Elevation and Depression",
        "Reference Angles",
        "Trigonometric Equations",
        "Trigonometric Functions"
    ],
    "Algebra": [
        "Quadratics",
        "Functions",
        "Logs",
        "Sequences & series",
        "Inequalities",
        "Sum and Difference of 2 Cubes",
        "Algebraic Fractions",
        "Simultaneous Equations in 2 Variables",
        "Simultaneous Equations in 3 Variables",
        "Simultaneous Equations with linear and non-linear Equations",
        "Manipulation of Formulae",
        "Surds"
    ],
    "Geometry of the Circle": [
        "Center (0,0) and radius r",
        "Center (h,k) and radius r",
        "Equations of the form x^2 +y^2 + 2gx + 2gy + c = 0",
        "Points outside, inside or on the Circle",
        "Intersection of a Line and Circle",
        "Equation of Tangent to a point on the Circle",
        "Equtaion of Tangents from point outside the Circle",
        "Touching Circles",
        "Problems in g,f and c"
    ],    
    "Geometry of the Line": [
        "Area of a Triangle",
        "Perpendicular Distance from a point to a Line",
        "Angle between 2 Lines"
    ],    
    "Integration": [
        "Trigonometric Integrals",
        "Algrabric Integrals",
        "Distance, Velocity, Acceleration",
        "Area under curves"
        
    ],
    "Statistics": [
        "Scatter Graphs",
        "Correlation Coefficient",
        "Mean, Mode, Median",
        "Range , Quartiles and Interquatile Range",
        "Standard Deviation",
        "z-scores",
        "Emperical Rule",
        "Central Limit Theroem",
        "Confidence Interval",
        "Hypothesis Testing"
    ],
    "Enlargements": [
        "Translation",
        "Central Symmetry",
        "Rotations",
        "Enlargement"
    ],
    "Complex Numbers": [
        "Addition and Subtraction of Complex Numbers",
        "Multiplication of Complex Numbers",
        "Division of Complex Numbers",
        "Roots of complex equations",
        "Polar Form of Complex Numbers",
        "De Moivres Theorem"
    ],
    "Differentation": [
        "Differentation From first Principles",
        "Chain Rule",
        "Product Rule",
        "Quotient Rule",
        "Natural Log Functions",
        "Trigonometric Functions",
        "Inverse Trigonometric Functions",
        "Second Derivative",
        "Local Maximum and Minimum",
        "Rates Of Change"
    ],
    
}

# -----------------------------
# SUBTOPIC SCOPE RULES
# Keeps a subtopic from drifting into a neighbouring one the student
# hasn't selected. If the student DOES select the avoided subtopic too
# (or uses Lucky Dip), the restriction is lifted automatically.
# To add more: add an entry to SUBTOPIC_RULES, describe the avoided
# subtopic in AVOID_DESCRIPTIONS, and list template keywords in
# TEMPLATE_BLOCKLIST.
# -----------------------------
SUBTOPIC_RULES = {
    "Polar Form of Complex Numbers": {
        "scope": ("converting between $a+bi$ and $r(\\cos\\theta + i\\sin\\theta)$, "
                  "finding modulus and argument (correct quadrant), "
                  "multiplying and dividing numbers already in polar form, "
                  "and representing them on an Argand diagram"),
        "avoid": ["De Moivres Theorem"],
    },
}

# What each "avoided" subtopic means, for the prompt
AVOID_DESCRIPTIONS = {
    "De Moivres Theorem": ("De Moivre's theorem, raising a complex number to a power "
                           "$n \\geq 3$, finding nth roots of a complex number, "
                           "or proof by induction"),
}

# Words that mark a past-paper template as belonging to that subtopic
TEMPLATE_BLOCKLIST = {
    "De Moivres Theorem": ["moivre", "nth root", "cube root", "induction"],
}


def scope_rules(subtopics):
    """Returns (prompt text, list of blocked template keywords)."""
    lines, blocked = [], []
    for s in subtopics:
        rule = SUBTOPIC_RULES.get(s)
        if not rule:
            continue
        lines.append(f"- For '{s}': only test {rule['scope']}.")
        for a in rule["avoid"]:
            if a in subtopics:  # student selected it too, so allow it
                continue
            lines.append(
                f"- Do NOT write any question, or any part of a question, involving "
                f"{AVOID_DESCRIPTIONS[a]}. That is a separate subsection the student has "
                f"not selected. If a question would naturally lead there, stop before that step."
            )
            blocked += TEMPLATE_BLOCKLIST.get(a, [])
    return "\n".join(lines), blocked


def add_scope_rules(system_prompt, rules):
    """Append scope rules AFTER the examples so they take priority."""
    if rules:
        system_prompt += f"\n\nSCOPE RULES (these override the examples above):\n{rules}"
    return system_prompt

# -----------------------------
# EXAM INDEX HELPERS
# -----------------------------
def find_template_questions(topic, difficulty=None, blocked=()):
    """Find relevant template questions from the exam index"""
    if not EXAM_INDEX:
        return []

    matching = []
    for q in EXAM_INDEX.get('questions', []):
        # Check if any topic matches
        if not any(topic.lower() in t.lower() for t in q.get('topics', [])):
            continue

        # Skip templates that belong to a subtopic the student hasn't selected
        if blocked:
            text = " ".join([q.get('description', ''),
                             *q.get('topics', []),
                             *q.get('concepts', [])]).lower()
            if any(b in text for b in blocked):
                continue

        if difficulty and q.get('difficulty', '').lower() != difficulty.lower():
            continue

        matching.append(q)

    return matching[:5]  # Return up to 5 templates


@st.cache_data(ttl=300)
def load_shared_worksheets(n=5):
    """Latest worksheets the admin has sent to all students.
    Errors are raised (not cached) so the tab can show what went wrong."""
    return _auth_supabase.rpc("get_shared_worksheets", {"n": n}).execute().data or []


@st.cache_data(ttl=300)
def load_shared_worksheet(ws_id):
    """One worksheet by id (used by the direct link in the email)."""
    try:
        rows = _auth_supabase.rpc("get_shared_worksheet", {"ws_id": int(ws_id)}).execute().data or []
        return rows[0] if rows else None
    except Exception:
        return None


def show_shared_worksheet(ws, key_prefix):
    """Render a shared worksheet with Show Answer buttons."""
    st.caption(f"{ws['topic']} · {ws['difficulty']}")
    for i, q in enumerate(ws.get("questions") or []):
        st.markdown(f"**Question {i + 1}**")
        st.markdown(q)
        if st.button("Show Answer", key=f"{key_prefix}_{ws['id']}_{i}"):
            with st.spinner("Working it out..."):
                st.markdown(generate_answer(q, ws["topic"], ws["difficulty"]))

def format_template_for_prompt(templates):
    """Format template questions for inclusion in AI prompt"""
    if not templates:
        return ""
    
    formatted = "\n\nREAL LEAVING CERT EXAM EXAMPLES (for style reference only):\n"
    for i, t in enumerate(templates, 1):
        formatted += f"\nExample {i}:\n"
        formatted += f"Question: {t.get('questionNumber', 'N/A')}\n"
        formatted += f"Topics: {', '.join(t.get('topics', []))}\n"
        formatted += f"Difficulty: {t.get('difficulty', 'N/A')}\n"
        formatted += f"Description: {t.get('description', 'N/A')}\n"
        formatted += f"Year/Paper: {t.get('paper', {}).get('year', 'N/A')} {t.get('paper', {}).get('paper', '')}\n"
    
    formatted += "\n⚠️ DO NOT copy these questions. Use them ONLY as style references to create NEW, ORIGINAL questions.\n"
    return formatted

# -----------------------------
# Claude CALL
# -----------------------------
def call_claude(system_prompt, user_prompt):
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    return "".join(
        block.text for block in response.content
        if block.type == "text"
    )


# -----------------------------
# LUCKY DIP HELPERS
# -----------------------------
def get_subtopics(topic):
    """Return subtopics with Lucky Dip always at the top."""
    return ["🎲 Lucky Dip"] + SUBTOPICS.get(topic, [])

def resolve_subtopics(topic, subtopics):
    """If Lucky Dip selected, return all real subtopics for this topic only."""
    if "🎲 Lucky Dip" in subtopics:
        return SUBTOPICS.get(topic, [])
    return subtopics

# -----------------------------
# ENHANCED WORKSHEET GENERATORS
# -----------------------------
def parse_numbered_questions(text):
    """
    Turn Claude's raw output into a clean list of questions.
    Skips a title/header line, keeps numbered questions, joins multi-line ones.
    """
    if not text:
        return []
    lines = text.split("\n")
    questions = []
    current = None
    start_re = re.compile(r'^\s*(?:question\s*)?(\d+)\s*[\.\):-]\s*(.*)', re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m = start_re.match(stripped)
        if m:
            if current is not None:
                questions.append(current.strip())
            current = m.group(2).strip()
        else:
            if current is not None:
                current += " " + stripped
    if current is not None:
        questions.append(current.strip())
    if not questions:
        cleaned = [l.strip() for l in lines if l.strip()]
        cleaned = [l for l in cleaned
                   if "worksheet" not in l.lower() and "difficulty" not in l.lower()]
        questions = cleaned
    return questions


def generate_worksheet(topic, subtopics, difficulty):
    subtopics = resolve_subtopics(topic, subtopics)
    chosen = ", ".join(subtopics)
    rules, blocked = scope_rules(subtopics)
    
    # Get template questions from exam index
    templates = find_template_questions(topic, difficulty, blocked)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate exactly 10 unique exam‑style questions that match REAL Leaving Cert exam style. "
        f"Difficulty level: {difficulty}. "
        f"Focus ONLY on these subtopics: {chosen}. "
        "Use LaTeX formatting for ALL mathematical expressions. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        "Return the questions as a numbered list, one per line, no solutions. "
        "\n"
        "IMPORTANT: The examples below are from REAL LC papers. "
        "Study their style, structure, and difficulty level, then create NEW questions inspired by this format."
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = (
        f"Create a {difficulty} worksheet on {topic}. "
        f"Subtopics: {chosen}. "
        "Generate 10 NEW questions that match the LC exam style shown in the examples. "
        "Ensure ALL maths is in LaTeX wrapped in $ ... $."
    )

    text = call_claude(system_prompt, user_prompt)
    return parse_numbered_questions(text)


def generate_balanced_worksheet(topic, subtopics):
    subtopics = resolve_subtopics(topic, subtopics)
    chosen = ", ".join(subtopics)
    rules, blocked = scope_rules(subtopics)
    
    # Get mixed difficulty templates
    templates = find_template_questions(topic, blocked=blocked)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate ONE exam‑style question for EACH selected subtopic. "
        "Match the authentic LC exam style shown in the reference examples. "
        "Use LaTeX formatting wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        "Return a numbered list, no solutions."
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = f"Topic: {topic}\nSubtopics: {chosen}\n\nCreate NEW questions matching LC exam style."

    text = call_claude(system_prompt, user_prompt)
    return parse_numbered_questions(text)


def generate_answer(question, topic, difficulty):
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Provide a full step‑by‑step worked solution. "
        "Use LaTeX formatting wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        f"Match the difficulty: {difficulty}."
    )

    user_prompt = f"Topic: {topic}\nQuestion: {question}"

    return call_claude(system_prompt, user_prompt)


def generate_similar_question(question, topic, difficulty, subtopics=None):
    # Scope rules only apply when we know which subtopics were selected
    rules, blocked = scope_rules(resolve_subtopics(topic, subtopics or []))

    # Get templates for better context
    templates = find_template_questions(topic, difficulty, blocked)
    template_context = format_template_for_prompt(templates[:2])  # Just 2 examples
    
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate ONE new question similar in style and difficulty but not identical. "
        "Follow authentic LC exam question format. "
        "Use LaTeX formatting wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        "No solution."
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = f"Topic: {topic}\nOriginal question: {question}\n\nCreate a NEW similar question."

    return call_claude(system_prompt, user_prompt)


def generate_exam_style_worksheet(topic, subtopics):
    subtopics = resolve_subtopics(topic, subtopics)
    chosen = ", ".join(subtopics)
    rules, blocked = scope_rules(subtopics)
    
    # Get exam templates
    templates = find_template_questions(topic, blocked=blocked)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths examiner. "
        "Generate questions that EXACTLY match the style, structure, tone, and difficulty "
        "of REAL LC Higher Level exam papers (see examples below). "
        "Base your style on typical LC question formats, multi‑part structure, "
        "the level of mathematical rigor expected. "
        "You may include multi‑part questions (a), (b), (c). "
        "You may include diagrams described in words. "
        "Do NOT quote or reproduce any past exam paper. "
        "Only create new, original questions inspired by the LC style shown in examples. "
        "Use LaTeX formatting for ALL mathematical expressions, wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        "Return exactly 3 exam‑style questions, each possibly multi‑part, no solutions."
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = (
        f"Topic: {topic}\n"
        f"Subtopics: {chosen}\n"
        "Generate 3 NEW exam‑style questions matching the LC format shown in examples."
    )

    text = call_claude(system_prompt, user_prompt)
    return parse_numbered_questions(text)


def generate_examPaper(topic, subtopics):
    subtopics = resolve_subtopics(topic, subtopics)
    chosen = ", ".join(subtopics)
    rules, blocked = scope_rules(subtopics)
    
    # Get exam templates for authentic style
    templates = find_template_questions(topic, blocked=blocked)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Certificate Higher Level Maths examiner. "
        "Generate NEW, original exam‑style questions that EXACTLY match the tone, structure, "
        "difficulty and progression of REAL LC Higher Level Maths papers (see examples below). "
        "Follow these rules strictly: "
        "- Match the authentic LC exam style shown in the reference examples "
        "- Use multi‑part structure (a), (b), (c) where appropriate "
        "- Include realistic LC‑style contexts and mathematical reasoning "
        "- Do NOT include marks for any part "
        "- ALL mathematical expressions must use LaTeX with $ ... $ delimiters "
        "- Never output plain‑text maths such as x^2, 1/6, sqrt(x) "
        "- Always use LaTeX forms such as $x^2$, $\\frac{1}{6}$, $\\sqrt{x}$ "
        "- Never copy, quote, or paraphrase any past exam paper "
        "- Create only NEW, original questions inspired by LC exam format "
        "- Return EXACTLY 3 exam‑style questions "
        "- Do NOT include solutions "
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = (
        f"Topic: {topic}\n"
        f"Subtopics: {chosen}\n"
        "Generate exactly 3 Higher Level exam‑style questions matching REAL LC exam format. "
        "Each question may contain multiple parts. "
        "Use LaTeX with $ ... $ for all maths. "
        "Return the questions separated by blank lines."
    )

    text = call_claude(system_prompt, user_prompt)

    questions = [q.strip() for q in text.split("\n\n") if q.strip()]
    return questions[:3]


def generate_from_descriptions(topic, descriptions, difficulty):
    """Write exactly one exam-style question for each description the admin typed."""
    numbered = "\n".join(f"{i}. {d}" for i, d in enumerate(descriptions, 1))
    system_prompt = (
        "You are a Leaving Certificate Higher Level Maths examiner. "
        "You will be given a numbered list of descriptions. For EACH description, write "
        "exactly ONE new, original exam-style question that tests exactly what it describes, "
        "in the same order. A question may have parts (a), (b), (c) written on the same line. "
        f"Difficulty: {difficulty}. "
        "Use LaTeX for ALL maths, inline with single dollar signs: $ ... $. "
        "Never use $$ ... $$ or plain-text maths such as x^2 or sqrt(x). "
        "Do NOT include solutions, marks, titles or the description itself. "
        "Separate the questions ONLY with the exact text: ---QUESTION BREAK---"
    )
    user_prompt = f"Topic: {topic}\n\nDescriptions:\n{numbered}"
    text = call_claude(system_prompt, user_prompt)
    qs = [q.strip() for q in text.split("---QUESTION BREAK---") if q.strip()]
    # keep each question as one block so blank-line splitting stays correct
    return [re.sub(r"\n\s*\n", "\n", q) for q in qs]


# -----------------------------
# MULTI-PART QUESTION GENERATOR
# -----------------------------
def generate_multipart_questions(topic, subtopics):
    subtopics = resolve_subtopics(topic, subtopics)
    chosen = ", ".join(subtopics)
    rules, blocked = scope_rules(subtopics)

    templates = find_template_questions(topic, blocked=blocked)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Certificate Higher Level Maths examiner. "
        "Generate exactly 2 multi-part exam questions in the style of REAL LC Higher Level papers. "
        "Each question MUST follow this structure: "
        "- A real-world or mathematical context introduced at the start "
        "- Parts (a), (b), (c), (d) that build progressively in difficulty "
        "- Do NOT include marks for any part "
        "- Part (a) should be straightforward, parts (c) and (d) should be challenging "
        "- Parts should be connected — later parts may use results from earlier parts "
        "- ALL mathematical expressions must use LaTeX with $ ... $ delimiters "
        "- Never use $$ ... $$ or plain text maths like x^2, sqrt(x) "
        "- Do NOT include solutions "
        "CRITICAL: Separate the two questions ONLY with the exact text: ---QUESTION BREAK--- "
        "Do not use any other separator. Each question must be complete with all its parts intact."
        f"{template_context}"
    )
    system_prompt = add_scope_rules(system_prompt, rules)

    user_prompt = (
        f"Topic: {topic}\n"
        f"Subtopics: {chosen}\n"
        "Generate 2 multi-part LC Higher Level exam questions. "
        "Each must have parts (a) through (c) or (d), building in difficulty. "
        "Use LaTeX with $ ... $ for all maths. "
        "Separate the two questions with exactly: ---QUESTION BREAK---"
    )

    text = call_claude(system_prompt, user_prompt)
    questions = [q.strip() for q in text.split("---QUESTION BREAK---") if q.strip()]
    return questions[:2]


# -----------------------------
# PAST PAPER BROWSER
# -----------------------------
def show_past_paper_questions(topic):
    """Display real past paper questions from the exam index"""
    if not EXAM_INDEX:
        st.warning("📚 Exam index not loaded. Upload exam-index.json to see past paper questions.")
        return
    
    # Get all questions for this topic
    matching = []
    for q in EXAM_INDEX.get('questions', []):
        if any(topic.lower() in t.lower() for t in q.get('topics', [])):
            matching.append(q)
    
    if not matching:
        st.info(f"No past paper questions found for {topic}. Try generating new questions!")
        return
    
    st.markdown(f"### 📖 Real LC Past Paper Questions - {topic}")
    st.caption(f"Found {len(matching)} questions from past papers")
    
    # Group by difficulty
    easy = [q for q in matching if q.get('difficulty') == 'Easy']
    medium = [q for q in matching if q.get('difficulty') == 'Medium']
    hard = [q for q in matching if q.get('difficulty') == 'Hard']
    
    # Show in tabs
    tab1, tab2, tab3 = st.tabs([f"Easy ({len(easy)})", f"Medium ({len(medium)})", f"Hard ({len(hard)})"])
    
    with tab1:
        display_past_paper_list(easy)
    
    with tab2:
        display_past_paper_list(medium)
    
    with tab3:
        display_past_paper_list(hard)

def display_past_paper_list(questions):
    """Display a list of past paper questions"""
    if not questions:
        st.info("No questions at this difficulty level")
        return
    
    for q in questions:
        # Build a unique key from the question's own data — guaranteed no clashes
        q_number = q.get('questionNumber', 'N/A')
        q_year = q.get('paper', {}).get('year', 'N/A')
        q_paper = q.get('paper', {}).get('paper', 'N/A').replace(' ', '')
        unique_key = f"past_{q_year}_{q_paper}_{q_number}"

        with st.expander(f"Q{q_number} - {q.get('description', 'No description')[:60]}..."):
            st.markdown(f"**Question:** {q_number}")
            st.markdown(f"**Paper:** {q_year} {q.get('paper', {}).get('paper', '')}")
            st.markdown(f"**Topics:** {', '.join(q.get('topics', []))}")
            st.markdown(f"**Difficulty:** {q.get('difficulty', 'N/A')}")
            st.markdown(f"**Concepts:** {', '.join(q.get('concepts', []))}")
            st.markdown(f"\n**Description:**")
            st.info(q.get('description', 'No description available'))
            
            # Generate similar button — unique key derived from question data
            if st.button(f"Generate Similar Question", key=unique_key):
                similar = generate_similar_question(
                    q.get('description', ''),
                    ', '.join(q.get('topics', [])),
                    q.get('difficulty', 'Medium')
                )
                st.markdown("**✨ New Question (Similar Style):**")
                st.markdown(similar)


# -----------------------------
# PAGE CONFIG
# -----------------------------
#st.set_page_config(page_title="LC Maths Tutor", layout="centered")

# REMOVE LEFT SIDEBAR COMPLETELY
st.markdown("""
    <style>
        /* Hide the entire sidebar */
        section[data-testid="stSidebar"] {
            display: none !important;
        }

        /* Expand main content to full width */
        div[data-testid="stAppViewBlockContainer"] {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        /* Optional: remove the blank space where the sidebar used to be */
        div[data-testid="stAppViewContainer"] > div:first-child {
            padding-left: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)


# -----------------------------
# BRAND HEADER
# -----------------------------
st.markdown(
    """
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1 style="margin-bottom:0;">📘 Leaving Certificate Honours Maths</h1>
        <p style="color:#4a4a4a; font-size:18px; margin-top:5px;">
            Adaptive, exam‑style practice — built for students.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# Show index status
if EXAM_INDEX:
    st.success(f"✅ Questions Loaded: {EXAM_INDEX.get('total_questions', 0)}")
else:
    st.warning("⚠️ Exam index not loaded - questions will be generated without LC past paper templates")

# -----------------------------
# MAIN NAVIGATION TABS
# -----------------------------

# -----------------------------
# WORKSHEET OPENED FROM AN EMAIL LINK (?worksheet=<id>)
# The link survives the login screen, so it opens straight after logging in.
# -----------------------------
_linked_id = st.query_params.get("worksheet")
if _linked_id and str(_linked_id).isdigit():
    _linked = load_shared_worksheet(int(_linked_id))
    if _linked:
        st.markdown(
            f"""
            <div style="background:#eef7ee;padding:16px;border-radius:10px;
                        border:1px solid #b9dcb9;margin-bottom:10px;">
                <h3 style="margin:0;">📬 {html.escape(_linked['title'])}</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        show_shared_worksheet(_linked, "link_ans")
        if st.button("Close worksheet", key="close_linked_ws"):
            del st.query_params["worksheet"]
            st.rerun()
        st.markdown("---")
    else:
        st.warning("Sorry, that worksheet couldn't be found.")

main_tab1, main_tab2 = st.tabs(["🎯 Generate New Questions", "📬 Shared Worksheets"])

with main_tab1:
    # -----------------------------
    # TOPIC + SUBTOPICS
    # -----------------------------
    st.markdown("### Choose Your Topic")
    topic = st.selectbox("", TOPICS, key="gen_topic")

    st.markdown("### Choose Subtopics")
    subtopics = st.multiselect(
        "",
        get_subtopics(topic),
        placeholder="Pick Subtopics",
        key="gen_subtopics"
    )

    st.markdown("---")

    # -----------------------------
    # SESSION STATE
    # -----------------------------
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "difficulty" not in st.session_state:
        st.session_state.difficulty = []
    if "similar_questions" not in st.session_state:
        st.session_state.similar_questions = {}

    # -----------------------------
    # WORKSHEET BUTTONS (MOBILE‑FIRST)
    # -----------------------------
    st.markdown("### Generate Exam Questions")

    # Row 1 — Difficulty
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Easy", use_container_width=True):
            st.session_state.difficulty = "Easy"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Easy")

    with c2:
        if st.button("Medium", use_container_width=True):
            st.session_state.difficulty = "Medium"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Medium")

    with c3:
        if st.button("Hard", use_container_width=True):
            st.session_state.difficulty = "Hard"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Hard")

    # Row 2 — Exam Style
    c4, = st.columns(1)

    with c4:
        if st.button("📝 Multi-Part Exam Questions", use_container_width=True):
            st.session_state.difficulty = "Exam Style"
            st.session_state.questions = generate_multipart_questions(topic, subtopics)

    st.markdown("---")

    # -----------------------------
    # DISPLAY WORKSHEET
    # -----------------------------
    questions = st.session_state.questions
    difficulty = st.session_state.difficulty

    if questions:
        st.markdown(
            f"""
            <h2 style="margin-bottom:0;">{topic} Exam Paper Questions</h2>
            <p style="color:#6a6a6a; margin-top:0;">
                Mode: <strong>{difficulty}</strong>
            </p>
            """,
            unsafe_allow_html=True
        )

        if subtopics:
            st.caption("Subtopics: " + ", ".join(subtopics))

        for i, q in enumerate(questions):
            if difficulty == "Exam Style":
                st.markdown(
                    f"""
                    <div style="
                        background:#f0f4ff;
                        padding:18px;
                        border-radius:10px;
                        margin-bottom:15px;
                        border:1px solid #c0ccee;
                    ">
                        <h4 style="margin-top:0;">📝 Question {i+1}</h4>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style="
                        background:#f7f9fc;
                        padding:18px;
                        border-radius:10px;
                        margin-bottom:15px;
                        border:1px solid #e3e6eb;
                    ">
                        <h4 style="margin-top:0;">Question {i+1}</h4>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.markdown(q)

            b1, b2 = st.columns(2)

            with b1:
                show_ans = st.button(f"Show Answer", key=f"ans_{i}", use_container_width=True)
            with b2:
                show_sim = st.button(f"More Like This", key=f"more_{i}", use_container_width=True)

            if show_ans:
                ans = generate_answer(q, topic, difficulty)
                st.markdown(ans)

            if show_sim:
                sim = generate_similar_question(q, topic, difficulty, subtopics)
                st.markdown("**Another question like this:**")
                st.markdown(sim)

    else:
        st.info("Choose a topic, pick subtopics, and select mode to begin.")

# -----------------------------
# SHARED WORKSHEETS (sent to all students from the admin panel)
# -----------------------------
with main_tab2:
    try:
        _sheets = load_shared_worksheets()
    except Exception as e:
        _sheets = []
        if st.session_state.get("email") == _ADMIN_EMAIL:
            st.error(f"Couldn't load shared worksheets (only you see this): {e}")
        else:
            st.warning("Shared worksheets are unavailable right now. Please try again later.")
    if not _sheets:
        st.info("No shared worksheets yet. Check back soon!")
    for _n, _ws in enumerate(_sheets):
        _when = str(_ws.get("created_at", ""))[:10]
        with st.expander(f"📄 {_ws['title']} ({_when})", expanded=(_n == 0)):
            show_shared_worksheet(_ws, "ws_ans")

# ===========================================================================
# ADMIN DASHBOARD  (two-factor: logged in as ADMIN_EMAIL + magic code to
# ADMIN_NOTIFY_EMAIL). Uses the service-role key, created ONLY inside the
# unlocked block. Provides: waitlist, user lookup, grant/revoke free access,
# stats, and GDPR delete.
# ===========================================================================
import random as _admin_random
from collections import Counter as _AdminCounter

def _admin_service_client():
    return create_client(_SUPABASE_URL, os.getenv("SUPABASE_SERVICE_KEY"))

if st.session_state.get("email") == _ADMIN_EMAIL:
    st.divider()
    st.subheader("🔒 Admin")

    st.session_state.setdefault("admin_unlocked", False)
    st.session_state.setdefault("admin_code_sent", False)

    # ---- two-factor unlock ----
    if not st.session_state.admin_unlocked:
        if not st.session_state.admin_code_sent:
            if st.button("Unlock admin (send me a code)"):
                _c = f"{_admin_random.randint(0, 999999):06d}"
                if _send_admin_code(_c):
                    st.session_state.admin_code = _c
                    st.session_state.admin_code_sent = True
                    st.rerun()
                else:
                    st.error("Couldn't send the admin code. Check Resend settings.")
        else:
            st.info("An unlock code was sent to your admin email.")
            _entered = st.text_input("Enter admin code", key="admin_code_entry")
            if st.button("Unlock"):
                if _entered.strip() == st.session_state.get("admin_code"):
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

    # ---- unlocked: the five panels ----
    else:
        _db = _admin_service_client()

        if st.button("Lock admin"):
            st.session_state.admin_unlocked = False
            st.rerun()

        _tabs = st.tabs([
            "📊 Stats", "🔎 Look up user", "🎁 Free access",
            "📝 Waitlist", "🗑️ Delete user", "📤 Send worksheet"
        ])

        # ---------- 1) STATS ----------
        with _tabs[0]:
            st.markdown("#### Overview")
            try:
                _users = _db.table("paid_users").select("*").execute().data or []
                _events = _db.table("login_events").select("*").execute().data or []
                _paid = sum(1 for u in _users if u.get("access_type", "paid") == "paid")
                _free = sum(1 for u in _users if u.get("access_type") == "free")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total users", len(_users))
                c2.metric("Paid", _paid)
                c3.metric("Free", _free)
                c4.metric("Total logins", len(_events))

                # signups in last 7 days (by paid_at)
                from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                _week_ago = _dt.now(_tz.utc) - _td(days=7)
                _recent = 0
                for u in _users:
                    ts = u.get("paid_at")
                    if ts:
                        try:
                            if _dt.fromisoformat(str(ts).replace("Z", "+00:00")) >= _week_ago:
                                _recent += 1
                        except Exception:
                            pass
                st.metric("New users (last 7 days)", _recent)
            except Exception as e:
                st.error(f"Couldn't load stats: {e}")

        # ---------- 2) LOOK UP USER ----------
        with _tabs[1]:
            st.markdown("#### Look up a user by email")
            _q = st.text_input("Email", key="lookup_email")
            if st.button("Look up"):
                _e = _q.strip().lower()
                if _e:
                    try:
                        _u = _db.table("paid_users").select("*").eq("email", _e).execute().data
                        if _u:
                            row = _u[0]
                            st.success(f"✅ {_e} has access ({row.get('access_type','paid')})")
                            st.write(f"Since: {row.get('paid_at','—')}")
                        else:
                            st.warning(f"❌ {_e} has NOT paid / no access.")
                        _logs = _db.table("login_events").select("*").eq("email", _e).execute().data or []
                        st.write(f"Login count: {len(_logs)}")
                        if _logs:
                            _last = max(l.get("logged_in_at","") for l in _logs)
                            st.write(f"Last login: {_last}")
                    except Exception as e:
                        st.error(f"Lookup failed: {e}")
                else:
                    st.error("Enter an email.")

        # ---------- 3) GRANT / REVOKE FREE ACCESS ----------
        with _tabs[2]:
            st.markdown("#### Grant free access")
            _fe = st.text_input("Email to grant free access", key="grant_email")
            if st.button("Grant free access"):
                _e = _fe.strip().lower()
                if _e:
                    try:
                        _db.table("paid_users").upsert(
                            {"email": _e, "access_type": "free"}
                        ).execute()
                        st.success(f"Granted free access to {_e}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                else:
                    st.error("Enter an email.")

            st.markdown("#### Revoke access")
            _re = st.text_input("Email to revoke access", key="revoke_email")
            if st.button("Revoke access"):
                _e = _re.strip().lower()
                if _e:
                    try:
                        _db.table("paid_users").delete().eq("email", _e).execute()
                        st.success(f"Revoked access for {_e}")
                    except Exception as e:
                        st.error(f"Failed: {e}")
                else:
                    st.error("Enter an email.")

        # ---------- 4) WAITLIST ----------
        with _tabs[3]:
            st.markdown("#### Waitlist signups")
            try:
                _wl = _db.table("waitlist").select("*").order("created_at", desc=True).execute().data or []
                if _wl:
                    # breakdown by level
                    _by_level = _AdminCounter(w.get("level","(unknown)") for w in _wl)
                    st.write("**By level:** " + ", ".join(f"{k}: {v}" for k, v in _by_level.items()))
                    st.dataframe(_wl, use_container_width=True)
                    # simple copy-paste export of emails
                    _emails = "\n".join(w.get("email","") for w in _wl)
                    st.text_area("All waitlist emails (copy to clipboard)", _emails, height=150)
                else:
                    st.info("No waitlist signups yet.")
            except Exception as e:
                st.error(f"Couldn't load waitlist: {e}")

        # ---------- 5) DELETE USER (GDPR) ----------
        with _tabs[4]:
            st.markdown("#### Delete a user's data (GDPR)")
            st.caption("Removes the user from paid_users and login_events. This is permanent.")
            _de = st.text_input("Email to delete", key="delete_email")
            _confirm = st.checkbox("I understand this permanently deletes their data")
            if st.button("Delete user data"):
                _e = _de.strip().lower()
                if not _e:
                    st.error("Enter an email.")
                elif not _confirm:
                    st.error("Tick the confirmation box first.")
                else:
                    try:
                        _db.table("paid_users").delete().eq("email", _e).execute()
                        _db.table("login_events").delete().eq("email", _e).execute()
                        _db.table("waitlist").delete().eq("email", _e).execute()
                        st.success(f"Deleted all data for {_e}")
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

        # ---------- 6) SEND WORKSHEET TO ALL STUDENTS ----------
        with _tabs[5]:
            st.markdown("#### Send a worksheet to every student")
            st.caption("Generate, edit, then send. Students see it in the 📬 Shared Worksheets "
                       "tab and get an email telling them it's there.")

            _bt = st.selectbox("Topic", TOPICS, key="bc_topic")
            _bs = st.multiselect("Subtopics", get_subtopics(_bt), key="bc_subtopics")
            _bd = st.radio("Difficulty", ["Easy", "Medium", "Hard"],
                           horizontal=True, key="bc_difficulty")

            st.markdown("**Option A:** generate 10 questions from the subtopics above")
            if st.button("Generate worksheet", key="bc_generate"):
                if not _bs:
                    st.error("Pick at least one subtopic (or Lucky Dip).")
                else:
                    with st.spinner("Generating..."):
                        _gen = generate_worksheet(_bt, _bs, _bd)
                    st.session_state.bc_text = "\n\n".join(_gen)
                    st.session_state.bc_title = f"{_bt} ({_bd})"

            st.markdown("**Option B:** describe the questions you want, one per line")
            _briefs_text = st.text_area(
                "Descriptions (one question is written for each line)",
                key="bc_briefs", height=150,
                placeholder="Complex number addition and subtraction\n"
                            "Find real and complex roots of a cubic",
            )
            if st.button("Generate from my descriptions", key="bc_generate_briefs"):
                _briefs = [re.sub(r"^\s*\d+\s*[\.\)]\s*", "", l).strip()
                           for l in (_briefs_text or "").splitlines() if l.strip()]
                if not _briefs:
                    st.error("Type at least one description.")
                else:
                    with st.spinner(f"Writing {len(_briefs)} questions..."):
                        _gen = generate_from_descriptions(_bt, _briefs, _bd)
                    st.session_state.bc_text = "\n\n".join(_gen)
                    st.session_state.bc_title = f"{_bt} ({_bd})"
                    if len(_gen) != len(_briefs):
                        st.warning(f"Asked for {len(_briefs)} questions but got {len(_gen)}. "
                                   "Check them below before sending.")

            st.markdown("**Then:** check and edit the questions below before sending")

            _title = st.text_input("Worksheet title", key="bc_title")
            _text = st.text_area(
                "Questions: leave a blank line between questions. Edit freely.",
                key="bc_text", height=350,
            )
            _bqs = [q.strip() for q in re.split(r"\n\s*\n", _text or "") if q.strip()]

            if _bqs:
                with st.expander(f"Preview as students will see it ({len(_bqs)} questions)"):
                    for _i, _q in enumerate(_bqs, 1):
                        st.markdown(f"**Question {_i}**")
                        st.markdown(_q)

            if st.button("Send a test email to me first", key="bc_test"):
                if not _ADMIN_NOTIFY_EMAIL:
                    st.error("ADMIN_NOTIFY_EMAIL isn't set.")
                else:
                    _ok, _bad = _send_worksheet_emails([_ADMIN_NOTIFY_EMAIL], _title or "Test worksheet")
                    if _ok:
                        st.success(f"Test sent to {_ADMIN_NOTIFY_EMAIL}")
                    else:
                        st.error("Test email failed. Check RESEND_API_KEY and WORKSHEET_FROM.")

            _bc_confirm = st.checkbox(
                "I've checked the questions and want to send this to ALL students",
                key="bc_confirm",
            )
            if st.button("Save & email all students", key="bc_send", type="primary"):
                if not _bqs or not (_title or "").strip():
                    st.error("Add a title and at least one question first.")
                elif not _bc_confirm:
                    st.error("Tick the confirmation box first.")
                else:
                    try:
                        _saved = _db.table("shared_worksheets").insert({
                            "title": _title.strip(),
                            "topic": _bt,
                            "subtopics": resolve_subtopics(_bt, _bs),
                            "difficulty": _bd,
                            "questions": _bqs,
                        }).execute()
                        _link = _worksheet_link(_saved.data[0]["id"])
                        load_shared_worksheets.clear()  # show it to students straight away
                    except Exception as e:
                        st.error(f"Couldn't save the worksheet: {e}")
                    else:
                        _all = _db.table("paid_users").select("*").execute().data or []
                        _to = sorted({u["email"] for u in _all
                                      if u.get("email") and not u.get("email_opt_out")})
                        with st.spinner(f"Emailing {len(_to)} students..."):
                            _ok, _bad = _send_worksheet_emails(_to, _title.strip(), _link)
                        st.success(f"Saved. Emailed {_ok} of {len(_to)} students.")
                        st.write(f"Direct link: {_link}")
                        if _bad:
                            st.warning(f"{len(_bad)} emails failed:")
                            st.text_area("Failed addresses", "\n".join(_bad), height=120)
