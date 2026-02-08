/**
 * Career Copilot - Frontend Chat Types
 * Standardized to match Backend Production Schema v2
 */

export interface Course {
    course_id: string;
    title: string;
    category?: string;
    level?: string;
    instructor?: string;
    description_short?: string;
    description_full?: string;
    cover?: string;
    reason?: string; // Matching backend 'reason' for recommendation
}

export interface ChatResponse {
    intent: string;
    answer: string;
    courses: Course[];
    categories: string[];
    next_actions: string[];
    session_state: Record<string, any>;
    session_id?: string;
    request_id?: string;
    meta?: Record<string, any>;
    errors?: string[];
}

export interface Message {
    id: string;
    type: 'user' | 'bot';
    content: string;
    timestamp: Date;
    data?: ChatResponse;
}
