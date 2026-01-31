import { create } from 'zustand';

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
    intent?: string;
    metadata?: any;
    // Common fields from API
    courses?: any[];
    projects?: any[];
    skill_groups?: any[];
    learning_plan?: any;
    dashboard?: any;
    catalog_browsing?: any;
}

interface AppState {
    messages: ChatMessage[];
    isLoading: boolean;
    userContext: {
        role?: string;
        skills?: string[];
    };
    addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
    setLoading: (loading: boolean) => void;
    updateContext: (context: Partial<AppState['userContext']>) => void;
    clearMessages: () => void;
}

export const useStore = create<AppState>((set) => ({
    messages: [],
    isLoading: false,
    userContext: {},

    addMessage: (msg: any) => set((state) => ({
        messages: [
            ...state.messages,
            {
                ...msg,
                id: msg.id || Math.random().toString(36).substr(2, 9),
                timestamp: Date.now(),
            }
        ]
    })),

    setLoading: (loading: boolean) => set({ isLoading: loading }),

    updateContext: (context) => set((state) => ({
        userContext: { ...state.userContext, ...context }
    })),

    clearMessages: () => set({ messages: [] })
}));
