import { ChatResponse, Course } from '../types/chat';

interface ChatRequest {
    session_id?: string;
    message: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';

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
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.answer || `API error: ${response.statusText}`);
    }

    return response.json();
}

export const uploadCV = async (file: File, sessionId?: string): Promise<ChatResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('session_id', sessionId);

    const response = await fetch(`${API_BASE_URL}/upload-cv`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        throw new Error('فشل رفع الملف');
    }

    return response.json();
}

export const fetchCourseDetails = async (courseId: string): Promise<Course> => {
    const response = await fetch(`${API_BASE_URL}/courses/${courseId}`);
    if (!response.ok) {
        throw new Error('فشل جلب تفاصيل الكورس');
    }
    return response.json();
}

export async function checkHealth(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
}
