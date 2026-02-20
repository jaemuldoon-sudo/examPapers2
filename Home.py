import streamlit as st
import os
import json
from anthropic import Anthropic

#PAGE CONFIG (MUST BE FIRST ST COMMAND)
st.set_page_config(page_title="Leaving Certificate Honours Maths", layout="centered")

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
TOPICS = ["Probability", "Trigonometry", "Algebra", "Geometry of the Circle", "Geometry of the Line", "Statistics", "Enlargements", "Calculus"]

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
    "Calculus": [
        "Differentiation",
        "Integration",
        "Rates of change",
        "Area under curves",
        "Product/Quotient/Chain rule"
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
  
}

# -----------------------------
# EXAM INDEX HELPERS
# -----------------------------
def find_template_questions(topic, difficulty=None):
    """Find relevant template questions from the exam index"""
    if not EXAM_INDEX:
        return []
    
    matching = []
    for q in EXAM_INDEX.get('questions', []):
        # Check if any topic matches
        topic_match = any(topic.lower() in t.lower() for t in q.get('topics', []))
        
        if topic_match:
            if difficulty:
                if q.get('difficulty', '').lower() == difficulty.lower():
                    matching.append(q)
            else:
                matching.append(q)
    
    return matching[:5]  # Return up to 5 templates

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
        model="claude-sonnet-4-20250514",  # Claude Sonnet 4
        max_tokens=4096,
        system=system_prompt,  # System prompt is separate in Claude
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.content[0].text


# -----------------------------
# ENHANCED WORKSHEET GENERATORS
# -----------------------------
def generate_worksheet(topic, subtopics, difficulty):
    chosen = ", ".join(subtopics)
    
    # Get template questions from exam index
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
        "\n"
        "IMPORTANT: The examples below are from REAL LC papers. "
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


def generate_balanced_worksheet(topic, subtopics):
    chosen = ", ".join(subtopics)
    
    # Get mixed difficulty templates
    templates = find_template_questions(topic)
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

    user_prompt = f"Topic: {topic}\nSubtopics: {chosen}\n\nCreate NEW questions matching LC exam style."

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


def generate_similar_question(question, topic, difficulty):
    # Get templates for better context
    templates = find_template_questions(topic, difficulty)
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

    user_prompt = f"Topic: {topic}\nOriginal question: {question}\n\nCreate a NEW similar question."

    return call_claude(system_prompt, user_prompt)


def generate_exam_style_worksheet(topic, subtopics):
    chosen = ", ".join(subtopics)
    
    # Get exam templates
    templates = find_template_questions(topic)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Cert Higher Level Maths examiner. "
        "Generate questions that EXACTLY match the style, structure, tone, and difficulty "
        "of REAL LC Higher Level exam papers (see examples below). "
        "Base your style on typical LC question formats, multi‑part structure, "
        "mark‑style progression, and the level of mathematical rigor expected. "
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

    user_prompt = (
        f"Topic: {topic}\n"
        f"Subtopics: {chosen}\n"
        "Generate 3 NEW exam‑style questions matching the LC format shown in examples."
    )

    text = call_claude(system_prompt, user_prompt)
    return [q.strip() for q in text.split("\n") if q.strip()]


def generate_examPaper(topic, subtopics):
    chosen = ", ".join(subtopics)
    
    # Get exam templates for authentic style
    templates = find_template_questions(topic)
    template_context = format_template_for_prompt(templates)

    system_prompt = (
        "You are a Leaving Certificate Higher Level Maths examiner. "
        "Generate NEW, original exam‑style questions that EXACTLY match the tone, structure, "
        "difficulty and progression of REAL LC Higher Level Maths papers (see examples below). "
        "Follow these rules strictly: "
        "- Match the authentic LC exam style shown in the reference examples "
        "- Use multi‑part structure (a), (b), (c) where appropriate "
        "- Include realistic LC‑style contexts and mathematical reasoning "
        "- Include marks for each part, e.g. '(a) [10 marks]' "
        "- ALL mathematical expressions must use LaTeX with $ ... $ delimiters "
        "- Never output plain‑text maths such as x^2, 1/6, sqrt(x) "
        "- Always use LaTeX forms such as $x^2$, $\\frac{1}{6}$, $\\sqrt{x}$ "
        "- Never copy, quote, or paraphrase any past exam paper "
        "- Create only NEW, original questions inspired by LC exam format "
        "- Return EXACTLY 3 exam‑style questions "
        "- Do NOT include solutions "
        f"{template_context}"
    )

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
    st.success(f"✅ Exam Index Loaded: {EXAM_INDEX.get('total_questions', 0)}")
else:
    st.warning("⚠️ Exam index not loaded - questions will be generated without LC past paper templates")

# -----------------------------
# MAIN NAVIGATION TABS
# -----------------------------

main_tab1, main_tab2 = st.tabs(["🎯 Generate New Questions", "Browse Past Papers"])

with main_tab1:
    # -----------------------------
    # TOPIC + SUBTOPICS
    # -----------------------------
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

    # Row 2 — Random / Balanced / Exam Style
  #  c4, c5, c6 = st.columns(3)

   # with c4:
   #     if st.button("Random", use_container_width=True):
   #         import random
   #         diff = random.choice(["Easy", "Medium", "Hard"])
   #         st.session_state.difficulty = diff
   #         st.session_state.questions = generate_worksheet(topic, subtopics, diff)

   # with c5:
   #     if st.button("Balanced", use_container_width=True):
   #         st.session_state.difficulty = "Balanced"
   #         st.session_state.questions = generate_balanced_worksheet(topic, subtopics)

   # with c6:
   #     if st.button("Exam Style", use_container_width=True):
   #         st.session_state.difficulty = "Exam Style"
   #         st.session_state.questions = generate_exam_style_worksheet(topic, subtopics)

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

with main_tab2:
    # -----------------------------
    # PAST PAPERS BROWSER
    # -----------------------------
    st.markdown("### Browse Real LC Past Paper Questions")
    
    if EXAM_INDEX:
        browse_topic = st.selectbox(
            "Select topic to browse:",
            TOPICS,
            key="browse_topic"
        )
        
        show_past_paper_questions(browse_topic)
    else:
        st.error("📚 Exam index not loaded. Please upload exam-index.json to your Railway deployment to browse past paper questions.")
        st.info("The exam index contains real LC past paper questions organized by topic, difficulty, and year.")