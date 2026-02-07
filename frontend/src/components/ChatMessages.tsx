"use client";

import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, User as UserIcon, Sparkles } from 'lucide-react';
import { Message } from '@/types/chat';
import { ChoicesPanel, CourseCard, PlanAccordion } from '@/components/ChatUI';
import { CVDashboard } from '@/components/CVDashboard';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Utility for this component
function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface ChatMessagesProps {
    messages: Message[];
    isLoading: boolean;
    onChoiceSelect: (choice: string) => void;
}

export default function ChatMessages({ messages, isLoading, onChoiceSelect }: ChatMessagesProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({
                top: scrollRef.current.scrollHeight,
                behavior: 'smooth'
            });
        }
    }, [messages, isLoading]);

    return (
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-12 py-8 scroll-smooth">
            <div className="max-w-4xl mx-auto space-y-8 pb-4">
                <AnimatePresence initial={false}>
                    {messages.map((msg, i) => (
                        <MessageBubble
                            key={msg.id}
                            msg={msg}
                            isLatestBotMessage={i === messages.length - 1 && msg.type === 'bot'}
                            isLoading={isLoading}
                            onChoiceSelect={onChoiceSelect}
                        />
                    ))}
                </AnimatePresence>

                {/* Loading Indicator */}
                {isLoading && (
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex justify-start pl-2"
                    >
                        <TypingIndicator />
                    </motion.div>
                )}
            </div>
        </div>
    );
}

// --- Local Components for cleaner file ---

const TypingIndicator = () => (
    <div className="flex space-x-1.5 space-x-reverse items-center p-3 px-4 glass-card rounded-2xl w-fit bg-slate-800/50 border border-white/5">
        <motion.div animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: 0 }} className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
        <motion.div animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }} className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
        <motion.div animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }} className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
    </div>
);

function MessageBubble({
    msg,
    isLatestBotMessage,
    isLoading,
    onChoiceSelect
}: {
    msg: Message,
    isLatestBotMessage: boolean,
    isLoading: boolean,
    onChoiceSelect: (c: string) => void
}) {
    const isBot = msg.type === 'bot';

    return (
        <motion.div
            initial={{ opacity: 0, y: 15, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className={cn(
                "flex w-full group",
                isBot ? "justify-start" : "justify-end"
            )}
        >
            <div className={cn(
                "flex gap-4 max-w-[90%] md:max-w-[80%]",
                isBot ? "flex-row" : "flex-row-reverse text-left"
            )}>
                {/* Avatar */}
                <div className={cn(
                    "w-8 h-8 md:w-10 md:h-10 rounded-2xl flex items-center justify-center shrink-0 border shadow-lg transition-transform group-hover:scale-105",
                    isBot ? "bg-slate-800 border-white/10" : "bg-blue-600 border-blue-500"
                )}>
                    {isBot ? <Bot className="w-5 h-5 text-blue-400" /> : <UserIcon className="w-5 h-5 text-white" />}
                </div>

                <div className="flex flex-col gap-2 w-full">
                    {/* Message Content */}
                    <div className={cn(
                        "p-4 rounded-[24px] shadow-sm text-sm md:text-base leading-relaxed whitespace-pre-wrap",
                        isBot
                            ? "glass-card text-slate-200 rounded-tr-none border border-white/5 bg-slate-900/40"
                            : "bg-blue-600 text-white rounded-tl-none shadow-blue-900/20"
                    )}>
                        {msg.content}
                    </div>

                    {/* Rich Data (Choices, Courses, Plan) */}
                    {isBot && msg.data && (
                        <div className="space-y-4 mt-2">
                            {/* Ask / Choices - Only if Latest */}
                            {msg.data.ask && isLatestBotMessage && (
                                <ChoicesPanel
                                    choices={msg.data.ask.choices}
                                    onSelect={onChoiceSelect}
                                    disabled={isLoading}
                                />
                            )}

                            {/* Courses */}
                            {msg.data.courses && msg.data.courses.length > 0 && (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest pl-2 mb-2">
                                        <Sparkles className="w-3 h-3 text-blue-400" />
                                        Recommended Screen
                                    </div>
                                    <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide -mx-2 px-2 snap-x">
                                        {msg.data.courses.map((course, idx) => (
                                            <div key={idx} className="snap-center">
                                                <CourseCard course={course} />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Learning Plan */}
                            {msg.data.learning_plan && (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
                                    <PlanAccordion plan={msg.data.learning_plan} />
                                </div>
                            )}

                            {/* CV Dashboard */}
                            {msg.data.dashboard && (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
                                    <div className="mt-4">
                                        <CVDashboard data={msg.data.dashboard} />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
