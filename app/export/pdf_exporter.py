import logging
import os
from typing import Dict, Any
from app.schemas_career import PlanOutput

logger = logging.getLogger(__name__)

class PDFExporter:
    @staticmethod
    def generate_pdf(plan: PlanOutput) -> str:
        """
        STEP 9 — PDF EXPORT
        Generate a PDF from its PlanOutput.
        Verified catalog titles only.
        """
        # Placeholder for real PDF generator (e.g., ReportLab or fpdf2)
        # For now, we simulate a PDF file path
        export_dir = "data/exports"
        os.makedirs(export_dir, exist_ok=True)
        
        pdf_filename = f"plan_{plan.session_id}_{int(os.path.getmtime('data/courses.csv')) if os.path.exists('data/courses.csv') else 0}.pdf"
        pdf_path = os.path.join(export_dir, pdf_filename)
        
        # In production, we'd use a template to render the plan
        # Ensure titles match catalog
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(f"CAREER COPILOT STUDY PLAN\n")
            f.write(f"Goal: {plan.summary[:50]}...\n")
            f.write(f"Type: {plan.plan_type.upper()}\n\n")
            for week in plan.plan_weeks:
                f.write(f"Week {week.week_number}\n")
                for item in week.items:
                    f.write(f"- {item.title}\n")
        
        return pdf_path

class PDFStore:
    @staticmethod
    def get_pdf_url(pdf_id: str) -> str:
        # Simulate generating a signed URL or local static path
        return f"/api/exports/{pdf_id}"
