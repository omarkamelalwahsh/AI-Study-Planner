from __future__ import annotations

from typing import List
import math

from src.schemas import LearningPlan, WeeklyPlan, Recommendation, UserProfile


# =========================
# DATA-ONLY LEARNING PLAN
# =========================
def build_learning_plan(user_profile: UserProfile, recommended_courses: List[Recommendation]) -> LearningPlan:
    """
    DATA-ONLY CONTRACT:
    - The plan is built ONLY from recommended_courses (which must be dataset-backed).
    - If no recommended_courses -> raise ValueError.
    - No invented tasks/tips/capstone. These fields are left empty.
    """
    if not recommended_courses:
        raise ValueError("No relevant course recommendations to build a learning plan.")

    # Strict: weeks must be int
    num_weeks = int(user_profile.plan_duration_weeks)
    if num_weeks <= 0:
        raise ValueError("plan_duration_weeks must be a positive integer.")

    total_hours_per_week = float(user_profile.hours_per_day) * float(user_profile.days_per_week)
    est_hours_each_week = round(total_hours_per_week, 2)

    # Distribute courses deterministically in ranked order
    chunk_size = max(1, math.ceil(len(recommended_courses) / num_weeks))

    weekly_schedule: List[WeeklyPlan] = []
    for week_idx in range(num_weeks):
        start = week_idx * chunk_size
        end = min((week_idx + 1) * chunk_size, len(recommended_courses))
        week_courses = recommended_courses[start:end]
        if not week_courses:
            break

        # Week title derived from dataset course titles only
        titles = [c.title for c in week_courses if getattr(c, "title", None)]
        week_title = f"Week {week_idx + 1}"

        topics = titles[:]  # data-only: topics are course titles
        courses = titles[:]  # data-only: show course titles only

        weekly_schedule.append(
            WeeklyPlan(
                week_title=week_title,
                topics=topics,
                courses=courses,
                estimated_hours=est_hours_each_week,
                mini_tasks=[],  # data-only: no tasks
            )
        )

    # Return learning plan with non-dataset fields empty
    return LearningPlan(
        recommended_courses=recommended_courses,
        weekly_schedule=weekly_schedule,
        capstone_project="",
        checklist=[],
        tips=[],
    )


def format_plan_as_markdown(plan: LearningPlan) -> str:
    """
    DATA-ONLY markdown: only shows dataset-backed course titles/links and week allocation.
    No invented text.
    """
    md = "# Learning Plan\n\n"

    # Recommended Courses
    md += "## Recommended Courses\n\n"
    md += "| Title | Level | Link |\n"
    md += "|------|-------|------|\n"
    for c in plan.recommended_courses:
        title = c.title if getattr(c, "title", None) else ""
        level = c.level if getattr(c, "level", None) else ""
        url = c.url if getattr(c, "url", None) else ""
        link = f"[Open]({url})" if url else ""
        md += f"| {title} | {level} | {link} |\n"
    md += "\n"

    # Weekly Schedule
    md += "## Weekly Schedule\n\n"
    for w in plan.weekly_schedule:
        md += f"### {w.week_title}\n\n"
        if w.courses:
            for course_title in w.courses:
                md += f"- {course_title}\n"
        else:
            md += "- (No courses assigned)\n"
        md += f"\n**Estimated Hours:** {w.estimated_hours}\n\n"

    return md


def export_plan_to_pdf(markdown_str: str) -> bytes | None:
    """
    Production-safe PDF export:
    - If fpdf not installed -> None
    - If Unicode/Arabic breaks core fonts -> None (no crash)
    """
    try:
        from fpdf import FPDF
    except Exception:
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    try:
        for line in markdown_str.splitlines():
            pdf.multi_cell(0, 8, txt=line)
        return pdf.output(dest="S").encode("latin-1", errors="ignore")
    except Exception:
        return None
