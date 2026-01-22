interface ChatRequest {
    session_id?: string;
    message: string;
}

interface CourseDetail {
    id: string;
    title: string;
    level?: string;
    category?: string;
    instructor?: string;
    duration_hours?: number;
    description?: string;
}

interface ErrorDetail {
    code: string;
    message: string;
}

interface ChatResponse {
    session_id: string;
    intent: string;
    answer: string;
    courses: CourseDetail[];
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

export async function checkHealth(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
}
