import { create } from 'zustand';

interface ChatMessage {
    id: string;
    sender: 'user' | 'assistant';
    text: string;
    timestamp: number;
    intent?: string;
    metadata?: any;
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

    addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => set((state) => ({
        messages: [
            ...state.messages,
            {
                ...msg,
                id: crypto.randomUUID(),
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
