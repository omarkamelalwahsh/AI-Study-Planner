export interface Course {
    course_id: string | number;
    title: string;
    category: string;
    level: string;
    instructor: string;
    description?: string;
    why_recommended?: string;
    thumbnail?: string;
}

export interface LearningItem {
    day_or_week: string;
    topics: string[];
    tasks: string[];
    deliverable?: string;
}

export interface LearningPlan {
    topic: string;
    duration: string;
    time_per_day: string;
    schedule: LearningItem[];
}

export interface ChoiceQuestion {
    question: string;
    choices: string[];
}

export interface ChatResponse {
    intent: string;
    language: 'ar' | 'en';
    answer: string;
    ask: ChoiceQuestion | null;
    courses: Course[];
    learning_plan: LearningPlan | null;
    projects: any[];
    one_question?: {
        question: string;
        choices: string[];
    };
    dashboard?: any; // Rich CV dashboard data
}

export interface Message {
    id: string;
    type: 'user' | 'bot';
    content: string;
    timestamp: Date;
    data?: ChatResponse;
}
