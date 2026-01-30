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

interface CVSection {
    title: string;
    score: number;
    status: string;
    notes: string;
}

interface CVDashboard {
    overall_score: number;
    sections: CVSection[];
    missing_keywords: string[];
    recommendations: string[];
}

interface ChatResponse {
    session_id: string;
    intent: string;
    answer: string;
    courses: CourseDetail[];
    projects: ProjectDetail[];
    skill_groups: SkillGroup[];
    learning_plan: LearningPlan | null;
    dashboard: CVDashboard | null;
    error: ErrorDetail | null;
    request_id: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
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

export async function uploadCV(file: File, sessionId?: string): Promise<ChatResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) {
        formData.append('session_id', sessionId);
    }

    const response = await fetch(`${API_BASE_URL}/upload-cv`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
}

export async function checkHealth(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
}
