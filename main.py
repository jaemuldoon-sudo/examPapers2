import streamlit as st
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# TOPICS + SUBTOPICS
# -----------------------------
TOPICS = ["Probability", "Trigonometry", "Algebra", "Circle", "Calculus"]

SUBTOPICS = {
    "Probability": [
        "Combined events",
        "Conditional probability",
        "Expected value",
        "Permutations and combinations",
        "Binomial distribution",
        "Bernoulli Trials",
        "Normal Distribution"
    ],
    "Trigonometry": [
        "Trig identities",
        "Trig equations",
        "Graphs",
        "Radians",
        "Sine rule / Cosine rule",
        "Unit Circle"
    ],
    "Algebra": [
        "Quadratics",
        "Functions",
        "Logs",
        "Sequences & series",
        "Inequalities"
    ],
    "Circle": [
        "Center (0,0) and radius r",
        "Center (h,k) and radius r",
        "Equations of the form x^2 +y^2 + 2gx + 2gy + c = 0",
        "Points outside, inside or on the Circle",
        "Intersection of a line and circle"
    ],
    "Calculus": [
        "Differentiation",
        "Integration",
        "Rates of change",
        "Area under curves",
        "Product/Quotient/Chain rule"
    ]
}

# -----------------------------
# OPENAI CALL
# -----------------------------
def call_openai(system_prompt, user_prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


# -----------------------------
# WORKSHEET GENERATORS
# -----------------------------
def generate_worksheet(topic, subtopics, difficulty):
    chosen = ", ".join(subtopics)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate exactly 10 unique exam‑style questions. "
        f"Difficulty level: {difficulty}. "
        f"Focus ONLY on these subtopics: {chosen}. "
        "Use LaTeX formatting for ALL mathematical expressions. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $."
        "Wrap EVERY LaTeX expression in $$ ... $$. "
        "Never use $$ ... $$ under any circumstances."
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc."
        "Every mathematical expression must be inside $ ... $."
        "Do NOT output plain text maths like x^2 or 1/6. "
        "Return the questions as a numbered list, one per line, no solutions."

    )

    user_prompt = (
        f"Create a {difficulty} worksheet on {topic}. "
        f"Subtopics: {chosen}. "
        "Ensure ALL maths is in LaTeX wrapped in $$ ... $$."
    )

    text = call_openai(system_prompt, user_prompt)
    return [q.strip() for q in text.split("\n") if q.strip()]


def generate_balanced_worksheet(topic, subtopics):
    chosen = ", ".join(subtopics)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate ONE exam‑style question for EACH selected subtopic. "
        "Use LaTeX formatting wrapped in $$ ... $$. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $."
        "Wrap EVERY LaTeX expression in $$ ... $$. "
        "Never use $$ ... $$ under any circumstances."
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc."
        "Every mathematical expression must be inside $ ... $."
        "Do NOT output plain text maths like x^2 or 1/6. "
        "Return a numbered list, no solutions."
    )

    user_prompt = f"Topic: {topic}\nSubtopics: {chosen}"

    text = call_openai(system_prompt, user_prompt)
    return [q.strip() for q in text.split("\n") if q.strip()]


def generate_answer(question, topic, difficulty):
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Provide a full step‑by‑step worked solution. "
        "Use LaTeX formatting wrapped in $$ ... $$. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $."
        "Wrap EVERY LaTeX expression in $$ ... $$. "
        "Never use $$ ... $$ under any circumstances."
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc."
        "Every mathematical expression must be inside $ ... $."
        "Do NOT output plain text maths like x^2 or 1/6. "
        f"Match the difficulty: {difficulty}."
    )

    user_prompt = f"Topic: {topic}\nQuestion: {question}"

    return call_openai(system_prompt, user_prompt)


def generate_similar_question(question, topic, difficulty):
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate ONE new question similar in style and difficulty "
        "but not identical. "
        "Use LaTeX formatting wrapped in $$ ... $$. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $."
        "Wrap EVERY LaTeX expression in $$ ... $$. "
        "Never use $$ ... $$ under any circumstances."
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc."
        "Every mathematical expression must be inside $ ... $."
        "Do NOT output plain text maths like x^2 or 1/6. "
        "No solution."
    )

    user_prompt = f"Topic: {topic}\nOriginal question: {question}"

    return call_openai(system_prompt, user_prompt)


def generate_worksheet(topic, subtopics, difficulty):
    chosen = ", ".join(subtopics)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Generate exactly 10 unique exam-style questions at the specified difficulty level and focused ONLY on the given subtopics. "
        "All mathematical expressions and variables must be formatted using inline LaTeX, wrapped in single dollar signs: $ ... $. "
        "Never use double dollar signs ($$ ... $$) under any circumstances. "
        "Never output plain text mathematics (such as x^2, 1/6, sqrt(x), etc.)—ALL must be enclosed in single dollar signs. "
        "Do NOT provide solutions—only questions. "
        "Return the questions as a numbered list, with one question per line. "
        "Every mathematical expression in LaTeX, wrapped with single dollar signs only."
    )

    user_prompt = (
        f"Create a {difficulty} worksheet on {topic}. "
        f"Subtopics: {chosen}. "
        "Ensure ALL maths is in LaTeX wrapped in single dollar signs ($ ... $), with NO double dollar signs ($$ ... $$) anywhere."
    )

    text = call_openai(system_prompt, user_prompt)
    return [q.strip() for q in text.split("\n") if q.strip()]




# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="LC Maths Tutor", layout="centered")

# -----------------------------
# BRAND HEADER
# -----------------------------
st.markdown(
    """
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1 style="margin-bottom:0;">📘 LC Maths Tutor</h1>
        <p style="color:#4a4a4a; font-size:18px; margin-top:5px;">
            Adaptive, exam‑style practice — built for students.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# TOPIC + SUBTOPICS
# -----------------------------
st.markdown("### Choose Your Topic")
topic = st.selectbox("", TOPICS)

st.markdown("### Choose Subtopics")
subtopics = st.multiselect(
    "",
    SUBTOPICS.get(topic, []),
    placeholder="Pick 1–5 subtopics"
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
st.markdown("### Generate Worksheet")

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

# Row 2 — Random / Balanced / Exam Style
c4, c5, c6 = st.columns(3)

with c4:
    if st.button("Random", use_container_width=True):
        import random
        diff = random.choice(["Easy", "Medium", "Hard"])
        st.session_state.difficulty = diff
        st.session_state.questions = generate_worksheet(topic, subtopics, diff)

with c5:
    if st.button("Balanced", use_container_width=True):
        # st.session_state.difficulty = "Balanced"
        st.session_state.questions = generate_balanced_worksheet(topic, subtopics)

with c6:
    if st.button("Exam Style", use_container_width=True):
        st.session_state.difficulty = "Exam Style"
        st.session_state.questions = generate_exam_style_worksheet(topic, subtopics)


st.markdown("---")

# -----------------------------
# DISPLAY WORKSHEET
# -----------------------------
questions = st.session_state.questions
difficulty = st.session_state.difficulty

if questions:
    st.markdown(
        f"""
        <h2 style="margin-bottom:0;">{topic} Worksheet</h2>
        <p style="color:#6a6a6a; margin-top:0;">
            Mode: <strong>{difficulty}</strong>
        </p>
        """,
        unsafe_allow_html=True
    )

    if subtopics:
        st.caption("Subtopics: " + ", ".join(subtopics))

    for i, q in enumerate(questions):
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
            if st.button(f"Show Answer", key=f"ans_{i}", use_container_width=True):
                ans = generate_answer(q, topic, difficulty)
                st.markdown(ans)

        with b2:
            if st.button(f"More Like This", key=f"more_{i}", use_container_width=True):
                sim = generate_similar_question(q, topic, difficulty)
                st.markdown("**Another question like this:**")
                st.markdown(sim)

else:
    st.info("Choose a topic, pick subtopics, and select a worksheet mode to begin.")
