import streamlit as st
import os
import json
import io
import re
from datetime import date
from anthropic import Anthropic
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# PAGE CONFIG (MUST BE FIRST ST COMMAND)
st.set_page_config(page_title="Leaving Certificate Honours Maths", layout="centered")

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# REMOVE LEFT SIDEBAR COMPLETELY
st.markdown("""
    <style>
        section[data-testid="stSidebar"] { display: none !important; }
        div[data-testid="stAppViewBlockContainer"] {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        div[data-testid="stAppViewContainer"] > div:first-child {
            padding-left: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------
# LOAD EXAM INDEX
# -----------------------------
def load_all_exam_indexes():
    files = [
        'JSON Files/exam-index1.json',
        'JSON Files/exam-index2.json',
        'JSON Files/exam-index3.json',
        'JSON Files/exam-index4.json',
        'JSON Files/exam-index5.json',
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
TOPICS = ["Probability", "Trigonometry", "Algebra", "Geometry of the Circle", "Geometry of the Line", "Statistics", "Enlargements", "Calculus", "Complex Numbers"]

SUBTOPICS = {
    "Probability": [
        "Combined events", "Conditional probability", "Expected value",
        "Permutations and combinations", "Binomial distribution", "Bernoulli Trials", "Normal Distribution"
    ],
    "Trigonometry": [
        "Trigonometric identities", "Graphs", "Radians", "Sine rule / Cosine rule",
        "Unit Circle", "Pytharagos Theorem", "Angles of Elevation and Depression",
        "Reference Angles", "Trigonometric Equations", "Trigonometric Functions"
    ],
    "Algebra": [
        "Quadratics", "Functions", "Logs", "Sequences & series", "Inequalities",
        "Sum and Difference of 2 Cubes", "Algebraic Fractions",
        "Simultaneous Equations in 2 Variables", "Simultaneous Equations in 3 Variables",
        "Simultaneous Equations with linear and non-linear Equations",
        "Manipulation of Formulae", "Surds"
    ],
    "Geometry of the Circle": [
        "Center (0,0) and radius r", "Center (h,k) and radius r",
        "Equations of the form x^2 +y^2 + 2gx + 2gy + c = 0",
        "Points outside, inside or on the Circle", "Intersection of a Line and Circle",
        "Equation of Tangent to a point on the Circle",
        "Equtaion of Tangents from point outside the Circle",
        "Touching Circles", "Problems in g,f and c"
    ],
    "Geometry of the Line": [
        "Area of a Triangle", "Perpendicular Distance from a point to a Line", "Angle between 2 Lines"
    ],
    "Calculus": [
        "Differentiation", "Integration", "Rates of change",
        "Area under curves", "Product/Quotient/Chain rule"
    ],
    "Statistics": [
        "Scatter Graphs", "Correlation Coefficient", "Mean, Mode, Median",
        "Range , Quartiles and Interquatile Range", "Standard Deviation",
        "z-scores", "Emperical Rule", "Central Limit Theroem",
        "Confidence Interval", "Hypothesis Testing"
    ],
    "Enlargements": ["Translation", "Central Symmetry", "Rotations", "Enlargement"],
    "Complex Numbers": [
        "Addition and Subtraction of Complex Numbers", "Multiplication of Complex Numbers",
        "Division of Complex Numbers", "Polar Form of Complex Numbers", "De Moivres Theorem"
    ],
}

# -----------------------------
# LATEX CLEANER FOR PDF
# -----------------------------
def clean_latex_for_pdf(text):
    """Convert LaTeX expressions to readable plain text for PDF output."""
    # Remove $ delimiters
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    # Common LaTeX conversions
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'sqrt(\1)', text)
    text = re.sub(r'\\sqrt', r'sqrt', text)
    text = re.sub(r'\^(\{[^}]+\})', lambda m: '^' + m.group(1).strip('{}'), text)
    text = re.sub(r'_(\{[^}]+\})', lambda m: '_' + m.group(1).strip('{}'), text)
    text = text.replace(r'\times', '×')
    text = text.replace(r'\div', '÷')
    text = text.replace(r'\pm', '±')
    text = text.replace(r'\leq', '≤')
    text = text.replace(r'\geq', '≥')
    text = text.replace(r'\neq', '≠')
    text = text.replace(r'\pi', 'π')
    text = text.replace(r'\theta', 'θ')
    text = text.replace(r'\alpha', 'α')
    text = text.replace(r'\beta', 'β')
    text = text.replace(r'\infty', '∞')
    text = text.replace(r'\sin', 'sin')
    text = text.replace(r'\cos', 'cos')
    text = text.replace(r'\tan', 'tan')
    text = text.replace(r'\log', 'log')
    text = text.replace(r'\ln', 'ln')
    text = text.replace(r'\left(', '(')
    text = text.replace(r'\right)', ')')
    text = text.replace(r'\left[', '[')
    text = text.replace(r'\right]', ']')
    text = text.replace(r'\{', '{')
    text = text.replace(r'\}', '}')
    text = re.sub(r'\\[a-zA-Z]+', '', text)  # Remove any remaining LaTeX commands
    return text.strip()

# -----------------------------
# PDF GENERATOR
# -----------------------------
def generate_pdf(title, topic, subtopics, difficulty, questions, include_answers=False, answers=None):
    """Generate a PDF for questions or answers and return as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=20,
        textColor=colors.HexColor('#1a3a5c'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#4a4a4a'),
        spaceAfter=4,
        alignment=TA_CENTER
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6a6a6a'),
        spaceAfter=2,
        alignment=TA_CENTER
    )
    question_num_style = ParagraphStyle(
        'QuestionNum',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#1a3a5c'),
        spaceBefore=14,
        spaceAfter=4,
        fontName='Helvetica-Bold'
    )
    question_style = ParagraphStyle(
        'Question',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=6,
        leading=16,
        leftIndent=10
    )
    answer_style = ParagraphStyle(
        'Answer',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1a5c1a'),
        spaceAfter=6,
        leading=16,
        leftIndent=10
    )

    story = []

    # --- HEADER ---
    story.append(Paragraph("Leaving Certificate Higher Level Maths", title_style))
    story.append(Paragraph(title, subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Topic: {topic}", meta_style))
    if subtopics:
        story.append(Paragraph(f"Subtopics: {', '.join(subtopics)}", meta_style))
    story.append(Paragraph(f"Difficulty: {difficulty}", meta_style))
    story.append(Paragraph(f"Date: {date.today().strftime('%d %B %Y')}", meta_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a3a5c')))
    story.append(Spacer(1, 12))

    # --- QUESTIONS / ANSWERS ---
    for i, q in enumerate(questions):
        clean_q = clean_latex_for_pdf(q)

        story.append(Paragraph(f"Question {i+1}", question_num_style))
        story.append(Paragraph(clean_q, question_style))

        if include_answers and answers and i < len(answers):
            clean_a = clean_latex_for_pdf(answers[i])
            story.append(Paragraph(f"Answer:", ParagraphStyle(
                'AnswerLabel',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor('#1a5c1a'),
                fontName='Helvetica-Bold',
                spaceBefore=4,
                leftIndent=10
            )))
            story.append(Paragraph(clean_a, answer_style))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e3e6eb')))

    # --- FOOTER NOTE ---
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Generated by LC Maths Tutor | Leaving Certificate Higher Level Mathematics",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                       textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER)
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------
# EXAM INDEX HELPERS
# -----------------------------
def find_template_questions(topic, difficulty=None):
    if not EXAM_INDEX:
        return []
    matching = []
    for q in EXAM_INDEX.get('questions', []):
        topic_match = any(topic.lower() in t.lower() for t in q.get('topics', []))
        if topic_match:
            if difficulty:
                if q.get('difficulty', '').lower() == difficulty.lower():
                    matching.append(q)
            else:
                matching.append(q)
    return matching[:5]

def format_template_for_prompt(templates):
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
# CLAUDE CALL
# -----------------------------
def call_claude(system_prompt, user_prompt):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return response.content[0].text

# -----------------------------
# WORKSHEET GENERATORS
# -----------------------------
def generate_worksheet(topic, subtopics, difficulty):
    chosen = ", ".join(subtopics)
    templates = find_template_questions(topic, difficulty)
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
        "\nIMPORTANT: The examples below are from REAL LC papers. "
        "Study their style, structure, and difficulty level, then create NEW questions inspired by this format."
        f"{template_context}"
    )
    user_prompt = (
        f"Create a {difficulty} worksheet on {topic}. "
        f"Subtopics: {chosen}. "
        "Generate 10 NEW questions that match the LC exam style shown in the examples. "
        "Ensure ALL maths is in LaTeX wrapped in $ ... $."
    )
    text = call_claude(system_prompt, user_prompt)
    return [q.strip() for q in text.split("\n") if q.strip()]


def generate_answer(question, topic, difficulty):
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Provide a full step‑by‑step worked solution matching LC marking scheme style. "
        "Use LaTeX formatting wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Never output plain text maths such as x^2, 1/6, sqrt(x), etc. "
        "Every mathematical expression must be inside $ ... $. "
        f"Match the difficulty: {difficulty}."
    )
    user_prompt = f"Topic: {topic}\nQuestion: {question}"
    return call_claude(system_prompt, user_prompt)


def generate_all_answers(questions, topic, difficulty):
    """Generate answers for all questions at once."""
    all_questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    system_prompt = (
        "You are a Leaving Cert Higher Level Maths tutor. "
        "Provide a full step‑by‑step worked solution for EACH question, matching LC marking scheme style. "
        "Number each answer to match the question number. "
        "Use LaTeX formatting wrapped in $ ... $. "
        "Use ONLY inline LaTeX with single dollar signs: $ ... $. "
        "Never use $$ ... $$ under any circumstances. "
        "Separate each answer with a blank line. "
        f"Match the difficulty: {difficulty}."
    )
    user_prompt = f"Topic: {topic}\n\nQuestions:\n{all_questions_text}\n\nProvide full worked solutions for all 10 questions."
    text = call_claude(system_prompt, user_prompt)
    # Split answers by blank lines
    answers = [a.strip() for a in text.split("\n\n") if a.strip()]
    return answers


def generate_similar_question(question, topic, difficulty):
    templates = find_template_questions(topic, difficulty)
    template_context = format_template_for_prompt(templates[:2])
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
    user_prompt = f"Topic: {topic}\nOriginal question: {question}\n\nCreate a NEW similar question."
    return call_claude(system_prompt, user_prompt)


# -----------------------------
# PAST PAPER BROWSER
# -----------------------------
def show_past_paper_questions(topic):
    if not EXAM_INDEX:
        st.warning("📚 Exam index not loaded.")
        return
    matching = []
    for q in EXAM_INDEX.get('questions', []):
        if any(topic.lower() in t.lower() for t in q.get('topics', [])):
            matching.append(q)
    if not matching:
        st.info(f"No past paper questions found for {topic}.")
        return
    st.markdown(f"### 📖 Real LC Past Paper Questions - {topic}")
    st.caption(f"Found {len(matching)} questions from past papers")
    easy   = [q for q in matching if q.get('difficulty') == 'Easy']
    medium = [q for q in matching if q.get('difficulty') == 'Medium']
    hard   = [q for q in matching if q.get('difficulty') == 'Hard']
    tab1, tab2, tab3 = st.tabs([f"Easy ({len(easy)})", f"Medium ({len(medium)})", f"Hard ({len(hard)})"])
    with tab1:
        display_past_paper_list(easy)
    with tab2:
        display_past_paper_list(medium)
    with tab3:
        display_past_paper_list(hard)

def display_past_paper_list(questions):
    if not questions:
        st.info("No questions at this difficulty level")
        return
    for q in questions:
        q_number = q.get('questionNumber', 'N/A')
        q_year   = q.get('paper', {}).get('year', 'N/A')
        q_paper  = q.get('paper', {}).get('paper', 'N/A').replace(' ', '')
        unique_key = f"past_{q_year}_{q_paper}_{q_number}"
        with st.expander(f"Q{q_number} - {q.get('description', 'No description')[:60]}..."):
            st.markdown(f"**Question:** {q_number}")
            st.markdown(f"**Paper:** {q_year} {q.get('paper', {}).get('paper', '')}")
            st.markdown(f"**Topics:** {', '.join(q.get('topics', []))}")
            st.markdown(f"**Difficulty:** {q.get('difficulty', 'N/A')}")
            st.markdown(f"**Concepts:** {', '.join(q.get('concepts', []))}")
            st.markdown(f"\n**Description:**")
            st.info(q.get('description', 'No description available'))
            if st.button(f"Generate Similar Question", key=unique_key):
                similar = generate_similar_question(
                    q.get('description', ''),
                    ', '.join(q.get('topics', [])),
                    q.get('difficulty', 'Medium')
                )
                st.markdown("**✨ New Question (Similar Style):**")
                st.markdown(similar)


# -----------------------------
# BRAND HEADER
# -----------------------------
st.markdown("""
    <div style="text-align:center; padding: 10px 0 20px 0;">
        <h1 style="margin-bottom:0;">📘 Leaving Certificate Honours Maths</h1>
        <p style="color:#4a4a4a; font-size:18px; margin-top:5px;">
            Adaptive, exam‑style practice — built for students.
        </p>
    </div>
""", unsafe_allow_html=True)

if EXAM_INDEX:
    st.success(f"✅ Questions Loaded: {EXAM_INDEX.get('total_questions', 0)}")
else:
    st.warning("⚠️ Exam index not loaded - questions will be generated without LC past paper templates")

# -----------------------------
# MAIN NAVIGATION TABS
# -----------------------------
main_tab1, main_tab2 = st.tabs(["🎯 Generate New Questions", "📖 Browse Past Papers"])

with main_tab1:

    st.markdown("### Choose Your Topic")
    topic = st.selectbox("", TOPICS, key="gen_topic")

    st.markdown("### Choose Subtopics")
    subtopics = st.multiselect(
        "",
        SUBTOPICS.get(topic, []),
        placeholder="Pick 1–5 subtopics",
        key="gen_subtopics"
    )

    st.markdown("---")

    # SESSION STATE
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "difficulty" not in st.session_state:
        st.session_state.difficulty = ""
    if "similar_questions" not in st.session_state:
        st.session_state.similar_questions = {}

    # -----------------------------
    # GENERATE EXAM QUESTIONS (existing)
    # -----------------------------
    st.markdown("### 🎯 Generate Exam Questions")
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

    st.markdown("---")

    # -----------------------------
    # GENERATE WORKSHEET PDF (new)
    # -----------------------------
    st.markdown("### 📄 Generate Worksheet PDF")
    st.caption("Generates 10 questions + a separate answer sheet — both as downloadable PDFs")

    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("📄 Easy PDF", use_container_width=True):
            st.session_state.difficulty = "Easy"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Easy")
            st.session_state.generate_pdf = True
    with p2:
        if st.button("📄 Medium PDF", use_container_width=True):
            st.session_state.difficulty = "Medium"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Medium")
            st.session_state.generate_pdf = True
    with p3:
        if st.button("📄 Hard PDF", use_container_width=True):
            st.session_state.difficulty = "Hard"
            st.session_state.questions = generate_worksheet(topic, subtopics, "Hard")
            st.session_state.generate_pdf = True

    # If PDF was just requested, generate and show download buttons
    if st.session_state.get("generate_pdf") and st.session_state.questions:
        with st.spinner("Generating questions PDF and answer sheet..."):
            questions  = st.session_state.questions
            difficulty = st.session_state.difficulty

            # Generate all answers at once
            answers = generate_all_answers(questions, topic, difficulty)

            # Build Questions PDF
            questions_pdf = generate_pdf(
                title="Worksheet — Questions",
                topic=topic,
                subtopics=subtopics,
                difficulty=difficulty,
                questions=questions,
                include_answers=False
            )

            # Build Answers PDF
            answers_pdf = generate_pdf(
                title="Worksheet — Worked Answers",
                topic=topic,
                subtopics=subtopics,
                difficulty=difficulty,
                questions=questions,
                include_answers=True,
                answers=answers
            )

        st.success("✅ PDFs ready to download!")
        col_q, col_a = st.columns(2)
        with col_q:
            st.download_button(
                label="⬇️ Download Questions PDF",
                data=questions_pdf,
                file_name=f"LC_Maths_{topic}_{difficulty}_Questions.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col_a:
            st.download_button(
                label="⬇️ Download Answers PDF",
                data=answers_pdf,
                file_name=f"LC_Maths_{topic}_{difficulty}_Answers.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # Reset flag
        st.session_state.generate_pdf = False

    st.markdown("---")

    # -----------------------------
    # DISPLAY QUESTIONS ON SCREEN (existing)
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

        # PDF download buttons also shown after questions on screen
        st.markdown("---")
        st.markdown("### 📄 Download These Questions as PDF")
        if st.button("📄 Generate PDF for these questions", use_container_width=True):
            with st.spinner("Generating PDFs..."):
                answers = generate_all_answers(questions, topic, difficulty)
                questions_pdf = generate_pdf(
                    title="Worksheet — Questions",
                    topic=topic,
                    subtopics=subtopics,
                    difficulty=difficulty,
                    questions=questions,
                    include_answers=False
                )
                answers_pdf = generate_pdf(
                    title="Worksheet — Worked Answers",
                    topic=topic,
                    subtopics=subtopics,
                    difficulty=difficulty,
                    questions=questions,
                    include_answers=True,
                    answers=answers
                )
            st.success("✅ PDFs ready!")
            col_q, col_a = st.columns(2)
            with col_q:
                st.download_button(
                    label="⬇️ Download Questions PDF",
                    data=questions_pdf,
                    file_name=f"LC_Maths_{topic}_{difficulty}_Questions.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            with col_a:
                st.download_button(
                    label="⬇️ Download Answers PDF",
                    data=answers_pdf,
                    file_name=f"LC_Maths_{topic}_{difficulty}_Answers.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
    else:
        st.info("Choose a topic, pick subtopics, and select mode to begin.")

with main_tab2:
    st.markdown("### Browse Real LC Past Paper Questions")
    if EXAM_INDEX:
        browse_topic = st.selectbox("Select topic to browse:", TOPICS, key="browse_topic")
        show_past_paper_questions(browse_topic)
    else:
        st.error("📚 Exam index not loaded.")
        st.info("The exam index contains real LC past paper questions organized by topic, difficulty, and year.")