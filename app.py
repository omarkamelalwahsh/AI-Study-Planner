import sys
import streamlit as st
import pandas as pd

from src.pipeline import CourseRecommenderPipeline
from src.schemas import RecommendRequest, UserProfile
from src.planner import build_learning_plan, format_plan_as_markdown, export_plan_to_pdf
from src.config import TOP_K_DEFAULT


# =========================
# STRICT MESSAGES (EN ONLY)
# =========================
NO_COURSES_MSG = "No relevant courses were found in our dataset for your request."


# =========================
# PYTHON VERSION ENFORCEMENT
# =========================
if not sys.version.startswith("3.11"):
    st.error("This application requires Python 3.11. Please run with Python 3.11 to continue.")
    st.stop()


# --- Page Config ---
st.set_page_config(
    page_title="Zedny Course Recommender",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Session State ---
if "pipeline" not in st.session_state:
    st.session_state.pipeline = None
if "recommendations" not in st.session_state:
    st.session_state["recommendations"] = []
if "learning_plan" not in st.session_state:
    st.session_state["learning_plan"] = None


@st.cache_resource
def get_pipeline():
    return CourseRecommenderPipeline()


# --- Custom CSS for Cards (kept as-is) ---
st.markdown(
    """
<style>
    .course-card {
        background-color: #1E1E1E;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .course-card:hover {
        transform: scale(1.02);
        border-color: #4CAF50;
    }
    .course-title {
        font-size: 20px;
        font-weight: bold;
        color: #4CAF50 !important;
        text-decoration: none;
        margin-bottom: 5px;
        display: block;
    }
    .course-meta {
        color: #888;
        font-size: 14px;
        margin-bottom: 10px;
    }
    .course-desc {
        color: #ddd;
        font-size: 15px;
        line-height: 1.5;
    }
    .score-badge {
        background-color: #2c2c2c;
        color: #4CAF50;
        padding: 3px 8px;
        border-radius: 5px;
        font-size: 12px;
        margin-left: 10px;
        font-weight: bold;
    }
    .why-section {
        margin-top: 10px;
        padding: 10px;
        background-color: #262626;
        border-radius: 5px;
        font-size: 13px;
        color: #aaa;
    }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    # PDF availability (production-safe)
    pdf_enabled = False
    try:
        import fpdf  # noqa: F401
        pdf_enabled = True
    except ImportError:
        pdf_enabled = False

    st.title("🎓 Zedny Smart Course Recommender")
    st.caption("AI-Powered Semantic Search | v2.1 - Strict & Stable")

    # Init Pipeline
    if st.session_state.pipeline is None:
        with st.spinner("Initializing AI Engine..."):
            try:
                st.session_state.pipeline = get_pipeline()
            except Exception as e:
                st.error(f"Failed to initialize system: {e}")
                st.stop()

    pipeline = st.session_state.pipeline

    # --- Sidebar Filters ---
    st.sidebar.header("🔍 Search Filters")

    categories = ["Any"]
    levels = ["Any"]

    # These columns must exist in your dataset; if they don't, keep only "Any"
    if getattr(pipeline, "courses_df", None) is not None:
        df0 = pipeline.courses_df
        if "category" in df0.columns:
            categories += sorted(df0["category"].dropna().unique().tolist())
        if "level" in df0.columns:
            levels += sorted(df0["level"].dropna().unique().tolist())

    sel_category = st.sidebar.selectbox("Category", categories)
    sel_level = st.sidebar.selectbox("Level", levels)
    top_k = st.sidebar.slider("Number of Results", 5, 50, TOP_K_DEFAULT)

    enable_rerank = st.sidebar.checkbox("Enable Deep Re-ranking (Slower)", value=False)
    show_debug = st.sidebar.checkbox("Show Debug Info", value=False)

    st.sidebar.markdown("---")
    st.sidebar.caption("v2.1 - Production")

    # --- Main Inputs ---
    st.header("🎯 Learning Plan Generator")

    col1, col2 = st.columns(2)

    with col1:
        topic = st.text_input(
            "What do you want to learn?",
            placeholder="e.g. Python, Machine Learning, SQL",
            key="topic",
        )
        current_level = st.selectbox(
            "Your current level?",
            ["Beginner", "Intermediate", "Advanced"],
            key="level",
        )
        goal = st.selectbox(
            "Your goal?",
            ["Get a job", "Build projects", "Improve in current work", "Pass an exam", "Learn basics"],
            key="goal",
        )

    with col2:
        hours_per_day = st.slider("Available time per day? (hours)", 0.5, 6.0, 2.0, 0.5, key="hours")
        days_per_week = st.slider("How many days/week?", 1, 7, 5, key="days")
        plan_duration = st.selectbox(
            "Plan duration?",
            [2, 4, 8, 12],
            key="duration",
            format_func=lambda x: f"{x} weeks",
        )

    preferred_content = st.selectbox("Preferred content type? (Optional)", ["Video", "Article", "Mixed"], index=2, key="content")
    budget = st.selectbox("Budget? (Optional)", ["Free", "Paid", "Any"], index=2, key="budget")

    generate_plan = st.button("🚀 Generate My Plan", type="primary")

    if generate_plan:
        # Reset previous outputs
        st.session_state["recommendations"] = []
        st.session_state["learning_plan"] = None

        # STEP 1: Validate input
        if not topic.strip():
            st.error("Please enter a topic to learn.")
            return

        try:
            user_profile = UserProfile(
                topic=topic.strip(),
                level=current_level,
                goal=goal,
                hours_per_day=hours_per_day,
                days_per_week=days_per_week,
                plan_duration_weeks=plan_duration,
                preferred_content=preferred_content,
                budget=budget,
            )
        except Exception as e:
            st.error(f"Invalid input: {e}")
            return

        # STEP 2: Build request (category filter only, do not force level)
        filters = {}
        if sel_category != "Any":
            filters["category"] = sel_category

        if sel_level != "Any":
            filters["level"] = sel_level

        request = RecommendRequest(
            query=topic.strip(),
            top_k=top_k,
            filters=filters if filters else None,
            enable_reranking=enable_rerank,
        )

        # STEP 3: Recommend
        with st.spinner("Searching dataset..."):
            try:
                response = pipeline.recommend(request)
            except Exception as e:
                st.error(f"Recommendation failed: {e}")
                return

        # IMPORTANT: keep these names aligned with your pipeline response object
        recs = getattr(response, "results", None)
        total_found = getattr(response, "total_found", None)

        # Curriculum ordering: Beginner -> Intermediate -> Advanced -> Other
        def _norm_level(x: str) -> str:
            return (x or "").strip().lower()

        beginner = [r for r in recs if _norm_level(getattr(r, "level", "")) == "beginner"]
        intermediate = [r for r in recs if _norm_level(getattr(r, "level", "")) == "intermediate"]
        advanced = [r for r in recs if _norm_level(getattr(r, "level", "")) == "advanced"]
        other = [r for r in recs if _norm_level(getattr(r, "level", "")) not in {"beginner", "intermediate", "advanced"}]
        recs = beginner + intermediate + advanced + other

        if not recs:
            st.warning(NO_COURSES_MSG)
            return

        # Persist recommendations
        st.session_state["recommendations"] = recs

        # DEBUG
        if show_debug:
            st.markdown("### Debug Info")
            st.write({"query": request.query, "top_k": request.top_k, "filters": request.filters, "rerank": request.enable_reranking})
            st.write(f"returned_count: {len(recs)}")

        # STEP 4: Display dataset-backed courses
        st.subheader("📚 Recommended Courses")

        # Map columns defensively (data-only: do not invent values)
        rows = []
        for r in recs:
            rows.append(
                {
                    "Title": getattr(r, "title", ""),
                    "Category": getattr(r, "category", ""),
                    "Level": getattr(r, "level", ""),
                    "URL": getattr(r, "url", ""),
                }
            )
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch")

        # STEP 5: Build plan strictly from recommendations
        try:
            plan = build_learning_plan(user_profile, recs)
            st.session_state["learning_plan"] = plan
        except Exception as e:
            st.error(f"Plan generation failed: {e}")
            return

        # STEP 6: Render plan (data-only)
        st.subheader("📅 Learning Plan (Weekly Schedule)")
        for week in plan.weekly_schedule:
            with st.expander(f"📖 {week.week_title}", expanded=False):
                st.write("**Courses:**")
                for c in week.courses:
                    st.write(f"- {c}")
                st.write(f"**Estimated Hours:** {week.estimated_hours}")

        # STEP 7: Downloads (data-only)
        markdown_plan = format_plan_as_markdown(plan)
        st.download_button(
            label="📥 Download Plan as Markdown",
            data=markdown_plan,
            file_name="learning_plan.md",
            mime="text/markdown",
        )

        if pdf_enabled:
            pdf_bytes = export_plan_to_pdf(markdown_plan)
            if not pdf_bytes:
                st.info("PDF export is unavailable for this content. Please download Markdown instead.")
            else:
                st.download_button(
                    label="📄 Download Plan as PDF",
                    data=pdf_bytes,
                    file_name="learning_plan.pdf",
                    mime="application/pdf",
                )


if __name__ == "__main__":
    main()
    