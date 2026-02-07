interface ChatRequest {
    session_id?: string;
    message: string;
}

interface CourseDetail {
    course_id: string;
    title: string;
    level?: string;
    category?: string;
    instructor?: string;
    duration_hours?: any;
    description?: string;
    description_short?: string;
    description_full?: string;
    cover?: string;
    reason?: string;
}

interface ProjectDetail {
    title: string;
    difficulty: string;
    description: string;
    deliverables: string[];
    suggested_tools: string[];
    // Legacy support
    level: string;
    skills: string[];
}

interface SkillGroup {
    skill_area: string;
    why_it_matters: string;
    skills: string[];
}

interface WeeklySchedule {
    week: number;
    focus: string;
    courses: string[];
    outcomes: string[];
}

interface LearningPlan {
    weeks?: number;
    hours_per_day?: number;
    schedule: WeeklySchedule[];
}

interface ErrorDetail {
    code: string;
    message: string;
}

interface Card {
    type: 'roadmap' | 'skills' | 'summary' | 'info';
    title: string;
    items?: string[];
    steps?: { title: string; desc: string; courses?: string[] }[];
    content?: string;
}

interface OneQuestion {
    question: string;
    choices: string[];
}

interface CVScore {
    overall: number;
    skills: number;
    experience: number;
    projects: number;
    marketReadiness: number;
    ats?: number;
    readiness?: number;
}

interface CVSkill {
    name: string;
    confidence: number;
}

interface CVRadarArea {
    area: string;
    value: number;
}

interface CVATSItem {
    id: string;
    text: string;
    done: boolean;
}

interface CVDashboard {
    candidate: {
        name: string;
        targetRole: string;
        seniority: string;
    };
    score: CVScore;
    roleFit: {
        detectedRoles: string[];
        direction: string;
        summary: string;
    };
    skills: {
        strong: CVSkill[];
        weak: CVSkill[];
        missing: CVSkill[];
    };
    radar: CVRadarArea[];
    projects: any[];
    atsChecklist: CVATSItem[];
    notes: {
        strengths: string;
        gaps: string;
    };
    recommendations: string[];
}

interface ChatResponse {
    session_id: string;
    intent: string;
    language: string;
    title: string;
    answer: string;
    cards: Card[];
    courses: CourseDetail[];
    one_question?: OneQuestion | null;

    // Metadata and internal tracker
    request_id: string;
    meta: any;
    flow_state_updates?: any;

    // Legacy support (to be phased out)
    all_relevant_courses?: CourseDetail[];
    projects?: ProjectDetail[];
    skill_groups?: SkillGroup[];
    catalog_browsing?: any | null;
    learning_plan?: LearningPlan | null;
    dashboard?: CVDashboard | null;
    error?: ErrorDetail | null;
    ask?: {
        question: string;
        choices: string[];
    };
    followup_question?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';
const API_BASE = API_BASE_URL;

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message,
            session_id: sessionId,
        } as ChatRequest),
    });

    if (!response.ok) {
        if (response.status === 503) {
            throw new Error('LLM is currently unavailable. Please try again.');
        }
        throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
}

export const uploadCV = async (file: File, sessionId?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) formData.append('session_id', sessionId)

    const response = await fetch(`${API_BASE}/upload-cv`, {
        method: 'POST',
        body: formData,
    })

    if (!response.ok) {
        throw new Error('فشل رفع الملف')
    }

    return response.json()
}

export const fetchCourseDetails = async (courseId: string) => {
    const response = await fetch(`${API_BASE}/courses/${courseId}`)
    if (!response.ok) {
        throw new Error('فشل جلب تفاصيل الكورس')
    }
    return response.json()
}


export async function checkHealth(): Promise<any> {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
}
