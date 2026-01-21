# app/core/formatting.py
from __future__ import annotations
from typing import Dict, List


def build_definition(topic: str, lang: str) -> str:
    # تعريفات قصيرة ثابتة
    topic = topic.lower()

    defs = {
        "sql": {
            "en": "SQL is the standard language for storing, manipulating and retrieving data in databases.",
            "ar": "SQL هي لغة استعلامات قياسية تُستخدم لإدارة واسترجاع البيانات من قواعد البيانات (خصوصًا MySQL)."
        },
        "python": {
            "en": "Python is a powerful, high-level programming language known for its readability and versatility.",
            "ar": "بايثون هي لغة برمجية قوية وعالية المستوى، مشهورة بسهولة قراءتها وتعدد استخداماتها."
        },
        "javascript": {
            "en": "JavaScript is the scripting language of the web, used to create interactive and dynamic content.",
            "ar": "جافاسكربت هي لغة البرمجة الأساسية للويب، تُستخدم لإنشاء محتوى تفاعلي وديناميكي."
        },
        "java": {
            "en": "Java is a high-level, class-based, object-oriented programming language that is designed to have as few implementation dependencies as possible.",
            "ar": "جافا هي لغة برمجة عالية المستوى، تعتمد على الكائنات (OOP)، ومصممة لتعمل على أي منصة دون تعديل."
        },
        "database": {
            "en": "Databases are organized systems for storing and managing digital information efficiently.",
            "ar": "قواعد البيانات هي أنظمة منظمة لتخزين وإدارة المعلومات الرقمية بكفاءة."
        },
        "illustrator": {
            "en": "Adobe Illustrator is the industry-standard vector graphics software for creating logos and illustrations.",
            "ar": "أدوبي إليستريتور هو البرنامج القياسي في الصناعة للرسوميات المتجهة (vectors)، يُستخدم لإنشاء الشعارات والرسوم التوضيحية."
        },
        "wordpress": {
            "en": "WordPress is the world's most popular tool for building websites without needing to write code from scratch.",
            "ar": "وردبريس هو الأداة الأكثر شهرة في العالم لبناء المواقع الإلكترونية دون الحاجة لكتابة كود من الصفر."
        },
        "excel": {
            "en": "Microsoft Excel is a powerful spreadsheet tool used for data analysis, calculations, and organization.",
            "ar": "مايكروسوفت إكسل هو أداة قوية للجداول البيانات، تُستخدم لتحليل البيانات، الحسابات، والتنظيم."
        },
        "cybersecurity": {
            "en": "Cybersecurity and ethical hacking involve protecting systems and networks from digital attacks and threats.",
            "ar": "الأمن السيبراني والاختراق الأخلاقي يشمل حماية الأنظمة والشبكات من الهجمات والتهديدات الرقمية."
        },
        "marketing": {
            "en": "Digital Marketing is the practice of promoting products and brands using the internet and social media.",
            "ar": "التسويق الرقمي هو ممارسة الترويج للمنتجات والعلامات التجارية باستخدام الإنترنت ووسائل التواصل الاجتماعي."
        },
        "management": {
            "en": "Project Management is the process of leading a team to achieve project goals within specific constraints.",
            "ar": "إدارة المشاريع هي عملية قيادة فريق لتحقيق أهداف المشروع ضمن قيود محددة."
        },
        "soft_skills": {
            "en": "Soft skills are interpersonal attributes that allow you to interact effectively with others in the workplace.",
            "ar": "المهارات الشخصية (Soft Skills) هي سمات تفاعلية تسمح لك بالتعامل بفعالية مع الآخرين في مكان العمل."
        },
        "php": {
            "en": "PHP is a popular general-purpose scripting language that is especially suited to web development.",
            "ar": "PHP هي لغة برمجة نصية شائعة للأغراض العامة، ومناسبة جداً لتطوير الويب."
        },
        "hr": {
            "en": "Human Resources (HR) focuses on managing people within an organization, from hiring to professional development.",
            "ar": "الموارد البشرية تنصب على إدارة الأفراد داخل المؤسسة، من التوظيف إلى التطوير المهني."
        }
    }
    return defs.get(topic, {}).get(lang, f"Starting your journey in {topic}...")


def build_uses(topic: str, lang: str) -> str:
    topic = topic.lower()
    uses = {
        "sql": {
            "en": "- Data Analysis & Reporting\n- Backend Development (MySQL/PostgreSQL)\n- Database Administration",
            "ar": "- تحليل البيانات وإعداد التقارير\n- تطوير الخلفية (Backend) مع MySQL\n- إدارة قواعد البيانات"
        },
        "python": {
            "en": "- Artificial Intelligence & Data Science\n- Web Development (Django/Flask)\n- Task Automation",
            "ar": "- الذكاء الاصطناعي وعلوم البيانات\n- تطوير الويب (Django/Flask)\n- أتمتة المهام المتكررة"
        },
        "javascript": {
            "en": "- Interactive Websites\n- Web Apps (React/Vue)\n- Server-side coding (Node.js)",
            "ar": "- المواقع الإلكترونية التفاعلية\n- تطبيقات الويب (React/Vue)\n- برمجة السيرفرات (Node.js)"
        },
        "java": {
             "en": "- Enterprise Applications\n- Android App Development\n- Large Systems Backward",
             "ar": "- تطبيقات الشركات الكبرى\n- تطوير تطبيقات الأندرويد\n- الأنظمة الخلفية الضخمة"
        },
        "database": {
            "en": "- Storing User Accounts\n- Financial Data Management\n- E-commerce Inventory",
            "ar": "- تخزين حسابات المستخدمين\n- إدارة البيانات المالية\n- جرد المنتجات في المتاجر الإلكترونية"
        },
        "management": {
            "en": "- Team Leadership\n- Project Planning\n- Strategic Decision Making",
            "ar": "- قيادة الفرق\n- تخطيط المشاريع\n- اتخاذ القرارات الاستراتيجية"
        },
        "business": {
            "en": "- Entrepreneurship\n- Financial Analysis\n- Market Strategy",
            "ar": "- ريادة الأعمال\n- التحليل المالي\n- استراتيجيات السوق"
        },
        "illustrator": {
            "en": "- Logo and Icon Design\n- Social Media Graphics\n- Print Layouts",
            "ar": "- تصميم الشعارات والأيقونات\n- رسومات وسائل التواصل الاجتماعي\n- المطبوعات والتنسيقات"
        },
        "wordpress": {
            "en": "- Personal Blogs & Portfolio Sites\n- Business Websites\n- E-commerce Stores (WooCommerce)",
            "ar": "- المدونات الشخصية ومواقع الأعمال\n- مواقع الشركات\n- المتاجر الإلكترونية (WooCommerce)"
        },
        "excel": {
            "en": "- Financial Reporting\n- Data Visualization\n- Business Planning",
            "ar": "- التقارير المالية\n- تمثيل البيانات بصرياً\n- التخطيط للأعمال"
        },
        "cybersecurity": {
            "en": "- Network Security Management\n- Ethical Hacking & Penetration Testing\n- Information Privacy Protection",
            "ar": "- إدارة أمن الشبكات\n- الاختراق الأخلاقي واختبار الاختراق\n- حماية خصوصية المعلومات"
        },
        "marketing": {
            "en": "- Social Media Strategy\n- Search Engine Optimization (SEO)\n- Content Strategy & Brand Building",
            "ar": "- استراتيجية وسائل التواصل الاجتماعي\n- تحسين محركات البحث (SEO)\n- استراتيجية المحتوى وبناء العلامة التجارية"
        },
        "management": {
            "en": "- Agile & Scrum Frameworks\n- Team Leadership\n- Risk Assessment & Resource Planning",
            "ar": "- إطارات عمل Agile و Scrum\n- قيادة الفرق\n- تقييم المخاطر وتخطيط الموارد"
        },
        "soft_skills": {
            "en": "- Effective Communication\n- Critical Thinking & Problem Solving\n- Conflict Resolution & Team Dynamics",
            "ar": "- التواصل الفعال\n- التفكير النقدي وحل المشكلات\n- حل النزاعات وديناميكيات الفريق"
        },
        "php": {
            "en": "- Web Development (Back-end)\n- Content Management Systems (WordPress)\n- Server-Side Scripting",
            "ar": "- تطوير الويب (Back-end)\n- أنظمة إدارة المحتوى (WordPress)\n- برمجة السيرفرات"
        },
        "hr": {
            "en": "- Recruitment & Interviewing\n- Employee Retention Strategies\n- Corporate Culture & Governance",
            "ar": "- التوظيف وإجراء المقابلات\n- استراتيجيات الحفاظ على الموظفين\n- الثقافة المؤسسية والحوكمة"
        }
    }
    default_en = "Common uses: Projects, Career skills, Practical applications."
    default_ar = "استخدامات شائعة: مشاريع وتطوير مهارات."
    return uses.get(topic, {}).get(lang, default_en if lang == "en" else default_ar)


def format_courses(grouped: Dict[str, List[dict]], lang: str) -> str:
    lines: List[str] = []
    # omit empty levels completely
    for lvl in ["Beginner", "Intermediate", "Advanced"]:
        items = grouped.get(lvl, [])
        if not items:
            continue
        lines.append(f"{lvl}:")
        for c in items:
            # course fields EXACT (English)
            lines.append(f"- {c['title']} — {c['category']} — {c['instructor']}")
    if not lines:
        return ""
    return "\n".join(lines)


def closure_question(lang: str) -> str:
    return (
        "Want a study plan using these courses? (yes/no)"
        if lang == "en"
        else "تحب أعملك خطة مذاكرة من الكورسات دي؟ (نعم/لا)"
    )


def build_study_plan(topic: str, courses: list[dict], lang: str = "ar", num_weeks: int = 4, hours_per_week: int = 10) -> dict:
    # 1. Distribute courses across weeks
    n = len(courses)
    
    # If user asks for more weeks than courses, some weeks might be empty or spread out.
    # If user asks for fewer weeks, we bunch them up.
    weeks = max(1, num_weeks)
    
    # Simple distribution: roughly equal chunks
    import math
    per_week = math.ceil(n / weeks)
    
    plan_weeks = []
    idx = 0
    for w in range(1, weeks + 1):
        if idx >= n:
            break # No more courses
            
        chunk = courses[idx : idx + per_week]
        idx += len(chunk)
        
        # Format tasks (course titles)
        tasks = [c["title"] for c in chunk]
        
        # Simple Milestone
        milestone = ""
        if lang == "en":
            milestone = f"Complete {len(chunk)} courses & Practice"
        else:
            milestone = f"إتمام {len(chunk)} كورسات وتطبيق عملي"

        plan_weeks.append({
            "week": w,
            "focus": f"{topic.title()} - Phase {w}" if lang == "en" else f"المرحلة {w} - {topic.title()}",
            "tasks": tasks,  # Frontend expects "tasks"
            "milestone": milestone,
            "estimated_hours": f"{hours_per_week} hrs/week"
        })

    # Generate text summary
    text_lines = []
    for w in plan_weeks:
        tasks_str = ", ".join(w["tasks"])
        if lang == "en":
            text_lines.append(f"Week {w['week']}: {tasks_str}")
        else:
            text_lines.append(f"الأسبوع {w['week']}: {tasks_str}")

    return {"weeks": plan_weeks, "text": "\n".join(text_lines)}
