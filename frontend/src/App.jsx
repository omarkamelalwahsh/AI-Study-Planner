import React, { useEffect } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { useChatStore } from './hooks/useChatStore';
import AppLayout from './components/AppLayout';
import Sidebar from './components/Sidebar';
import ChatArea from './components/Chat/ChatArea';
import './index.css';
import { api } from './api';

function AppContent() {
    const {
        chats,
        activeChatId,
        setActiveChatId,
        createChat,
        deleteChat,
        addMessage,
        updateMessageContent,
        clearChat,
        updateClientState,
        activeChat
    } = useChatStore();

    // Real API integration
    // Real API integration
    const handleSendMessage = async (text) => {
        if (!activeChatId) return;

        // 1. Add User Message
        addMessage('user', text);

        // 2. Prepare payload
        const history = activeChat?.messages?.map(m => ({
            role: m.role,
            content: m.content
        })) || [];

        const messagesPayload = [...history, { role: 'user', content: text }];

        // 3. Add Placeholder Assistant Message with metadata support
        const assistantMessageId = Math.random().toString(36).substr(2, 9);
        addMessage('assistant', '...', assistantMessageId, {
            courses: [],
            study_plan: []
        });

        try {
            // Pass client_state from the active chat
            const data = await api.sendMessage(messagesPayload, activeChatId, activeChat?.client_state);

            // Update client_state if returned
            if (data?.client_state) {
                updateClientState(activeChatId, data.client_state);
            }

            updateMessageContent(activeChatId, assistantMessageId, {
                content: data?.message || "مفيش رد حالياً.",
                courses: Array.isArray(data?.courses) ? data.courses : [],
                study_plan: Array.isArray(data?.study_plan) ? data.study_plan : []
            });

        } catch (error) {
            console.error('Error sending message:', error);
            updateMessageContent(activeChatId, assistantMessageId, {
                content: "Sorry, I encountered an error. Please try again."
            });
        }
    };

    return (
        <AppLayout
            sidebar={
                <Sidebar
                    chats={chats}
                    activeChatId={activeChatId}
                    onSelectChat={setActiveChatId}
                    onNewChat={createChat}
                    onDeleteChat={deleteChat}
                />
            }
            content={
                <ChatArea
                    activeChat={activeChat}
                    onSendMessage={handleSendMessage}
                    onClearChat={clearChat}
                />
            }
        />
    );
}

function App() {
    return (
        <ThemeProvider>
            <AppContent />
        </ThemeProvider>
    );
}

export default App;
