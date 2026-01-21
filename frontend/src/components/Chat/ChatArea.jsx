import React, { useEffect, useRef } from 'react';
import { Trash2 } from 'lucide-react';
import MessageBubble from './MessageBubble';
import Composer from './Composer';

const ChatArea = ({ activeChat, onSendMessage, onClearChat }) => {
    const scrollRef = useRef(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [activeChat?.messages]); // Depend on messages length

    const isEmpty = !activeChat?.messages?.length;

    const handleSuggestionClick = (suggestion) => {
        onSendMessage(suggestion);
    };

    return (
        <div className="flex flex-col h-full w-full bg-bg-primary relative">

            {/* Header */}
            <header className="flex-none h-14 border-b border-border flex items-center px-4 justify-between bg-bg-primary/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center gap-2 overflow-hidden">
                    <span className="font-semibold text-text-primary truncate">
                        {activeChat?.title || 'New Chat'}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-500 text-xs font-medium border border-green-500/20">
                        Connected
                    </span>
                </div>

                {/* Clear Chat Button */}
                {!isEmpty && (
                    <button
                        onClick={() => {
                            if (window.confirm("هل متأكد انك عايز تمسح الشات؟")) {
                                onClearChat();
                            }
                        }}
                        className="p-2 text-text-secondary hover:text-red-500 hover:bg-red-500/10 rounded-md transition-colors"
                        title="Clear Chat"
                    >
                        <Trash2 size={18} />
                    </button>
                )}
            </header>

            {/* Scrollable Message Area */}
            <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth" ref={scrollRef}>
                {isEmpty ? (
                    <div className="h-full flex flex-col items-center justify-center p-8 text-center animate-in fade-in duration-500">
                        <h2 className="text-2xl font-bold text-text-primary mb-2">How can I help you today?</h2>
                    </div>
                ) : (
                    <div className="flex flex-col w-full pb-8">
                        {activeChat.messages.map((msg) => (
                            <MessageBubble key={msg.id} message={msg} />
                        ))}
                    </div>
                )}
            </div>

            {/* Composer Footer */}
            <div className="flex-none bg-bg-primary">
                <Composer onSend={onSendMessage} disabled={false} />
            </div>
        </div>
    );
};

export default ChatArea;
