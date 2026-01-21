import { useState, useEffect } from 'react';

// Generate a random ID
const generateId = () => Math.random().toString(36).substr(2, 9);

export const useChatStore = () => {
    const [chats, setChats] = useState(() => {
        try {
            const stored = localStorage.getItem('chats');
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (e) {
            console.error("Failed to load chats", e);
        }
        // Default initial chat
        const initialId = generateId();
        return [{ id: initialId, title: 'New Chat', messages: [], client_state: {} }];
    });

    const [activeChatId, setActiveChatId] = useState(() => {
        try {
            const stored = localStorage.getItem('activeChatId');
            if (stored) return stored;
        } catch (e) { console.error(e) }
        return chats[0]?.id; // Default to first chat ID if available
    });

    // Persist to local storage
    useEffect(() => {
        localStorage.setItem('chats', JSON.stringify(chats));
        localStorage.setItem('activeChatId', activeChatId);
    }, [chats, activeChatId]);

    const activeChat = chats.find(c => c.id === activeChatId) || chats[0];

    // Actions
    const createChat = () => {
        const newChat = { id: generateId(), title: 'New Chat', messages: [], client_state: {} };
        setChats(prev => [newChat, ...prev]);
        setActiveChatId(newChat.id);
    };

    const deleteChat = (id) => {
        const newChats = chats.filter(c => c.id !== id);
        if (newChats.length === 0) {
            // Always keep at least one chat
            const newChat = { id: generateId(), title: 'New Chat', messages: [] };
            setChats([newChat]);
            setActiveChatId(newChat.id);
        } else {
            setChats(newChats);
            if (id === activeChatId) {
                setActiveChatId(newChats[0].id);
            }
        }
    };

    const addMessage = (role, text, customId = null, metadata = {}) => {
        if (!activeChatId) return;

        setChats(prev => prev.map(chat => {
            if (chat.id === activeChatId) {
                const messageId = customId || generateId();
                const updatedMessages = [
                    ...chat.messages,
                    {
                        id: messageId,
                        role,
                        content: text,
                        timestamp: Date.now(),
                        ...metadata
                    }
                ];

                // Update title if it's the first user message and title is "New Chat"
                let updatedTitle = chat.title;
                if (chat.title === 'New Chat' && role === 'user') {
                    updatedTitle = text.slice(0, 30) + (text.length > 30 ? '...' : '');
                }

                return {
                    ...chat,
                    title: updatedTitle,
                    messages: updatedMessages
                };
            }
            return chat;
        }));
    };

    const updateMessageContent = (chatId, messageId, updates) => {
        setChats(prevChats => prevChats.map(chat => {
            if (chat.id === chatId) {
                return {
                    ...chat,
                    messages: chat.messages.map(msg => {
                        if (msg.id === messageId) {
                            // Support functional updates or static objects
                            const patch = typeof updates === 'function' ? updates(msg) : updates;
                            // Ensure patch is treated as object if it's a string
                            const cleanPatch = typeof patch === 'string' ? { content: patch } : patch;
                            return { ...msg, ...cleanPatch };
                        }
                        return msg;
                    })
                };
            }
            return chat;
        }));
    };

    const clearChat = () => {
        setChats(prev => prev.map(chat => {
            if (chat.id === activeChatId) {
                return { ...chat, messages: [], client_state: {} };
            }
            return chat;
        }));
    };

    const updateClientState = (chatId, state) => {
        setChats(prev => prev.map(chat => {
            if (chat.id === chatId) {
                return { ...chat, client_state: state };
            }
            return chat;
        }));
    };

    return {
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
    };
};
