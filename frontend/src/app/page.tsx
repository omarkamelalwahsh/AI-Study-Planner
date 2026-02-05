"use client";

import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Menu, User as UserIcon } from 'lucide-react';
import toast from 'react-hot-toast';

// New Components
import LayoutShell from '@/components/LayoutShell';
import Sidebar from '@/components/Sidebar';
import WelcomeHero from '@/components/WelcomeHero';
import ChatMessages from '@/components/ChatMessages';
import ChatInput from '@/components/ChatInput';

// Types
import { Message, ChatResponse } from '@/types/chat';

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState(`session_${Date.now()}`);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    // --- Actions ---

    const handleSend = async (text?: string) => {
        const msgText = text || input.trim();
        if (!msgText || isLoading) return;

        // Optimistic UI Update
        const userMsg: Message = {
            id: Date.now().toString(),
            type: 'user',
            content: msgText,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/chat', { // Use relative path via Next.js rewrite
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: msgText,
                    session_id: sessionId
                })
            });

            if (!response.ok) throw new Error('Network response was not ok');
            const data: ChatResponse = await response.json();

            const botMsg: Message = {
                id: (Date.now() + 1).toString(),
                type: 'bot',
                content: data.answer,
                timestamp: new Date(),
                data: data
            };
            setMessages(prev => [...prev, botMsg]);
        } catch (error) {
            console.error(error);
            toast.error("حصلت مشكلة بسيطة... ياريت تجرب تاني");
        } finally {
            setIsLoading(false);
        }
    };

    const startNewChat = () => {
        setMessages([]);
        setSessionId(`session_${Date.now()}`);
        toast.success("بدأت محادثة جديدة");
    };

    // --- Render Logic ---
    const showHero = messages.length === 0;

    return (
        <LayoutShell>
            {/* 1. Sidebar (Relative, Collapsible) */}
            <Sidebar
                isOpen={isSidebarOpen}
                onNewChat={startNewChat}
            />

            {/* 2. Main Content Column */}
            <main className="flex-1 flex flex-col relative w-full h-full min-w-0 bg-transparent">

                {/* Header (Shrink-0, Fixed Height) */}
                <header className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-white/5 bg-slate-950/20 backdrop-blur-sm z-30 relative">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="p-2 hover:bg-white/5 rounded-lg text-slate-400 transition-colors"
                        >
                            <Menu className="w-5 h-5" />
                        </button>
                        <div className="flex flex-col">
                            <span className="font-bold text-sm text-slate-100">مساعد كارير كوبايلوت</span>
                            <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                متصل الآن
                            </span>
                        </div>
                    </div>

                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 border border-white/20 flex items-center justify-center">
                        <UserIcon className="w-4 h-4 text-white" />
                    </div>
                </header>

                {/* View Resolver: Hero vs Chat */}
                <div className="flex-1 overflow-hidden flex flex-col relative">
                    <AnimatePresence mode="wait">
                        {showHero ? (
                            <motion.div
                                key="hero"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="w-full h-full"
                            >
                                <WelcomeHero onSelectPrompt={handleSend} />
                            </motion.div>
                        ) : (
                            <motion.div
                                key="chat"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex flex-col w-full h-full"
                            >
                                <ChatMessages
                                    messages={messages}
                                    isLoading={isLoading}
                                    onChoiceSelect={handleSend}
                                />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Input Area (Always visible at bottom) */}
                <ChatInput
                    value={input}
                    onChange={setInput}
                    onSend={() => handleSend()}
                    isLoading={isLoading}
                />
            </main>
        </LayoutShell>
    );
}
