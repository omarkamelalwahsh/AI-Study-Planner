"use client";

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Send, Sparkles, BookOpen, Map, ChevronDown, User, Bot,
    MessageSquare, Plus, PlusCircle, LayoutDashboard, History,
    ExternalLink, GraduationCap, Briefcase, Clock, CheckCircle2,
    Image as ImageIcon, MoreHorizontal
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** UTILS */
function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

/** TYPES */
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
}

export interface Message {
    id: string;
    type: 'user' | 'bot';
    content: string;
    timestamp: Date;
    data?: ChatResponse;
}

/** COMPONENTS */

/** Typing Indicator */
export const TypingIndicator = () => (
    <div className="flex space-x-1.5 space-x-reverse items-center p-3 px-4 glass-card rounded-2xl w-fit">
        <motion.div
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
            className="w-1.5 h-1.5 bg-blue-400 rounded-full"
        />
        <motion.div
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
            className="w-1.5 h-1.5 bg-blue-400 rounded-full"
        />
        <motion.div
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
            className="w-1.5 h-1.5 bg-blue-400 rounded-full"
        />
    </div>
);

/** Choice Panel */
export const ChoicesPanel = ({
    choices,
    onSelect,
    disabled
}: {
    choices: string[],
    onSelect: (choice: string) => void,
    disabled: boolean
}) => (
    <div className="flex flex-wrap gap-2 mt-4 justify-start overflow-x-auto pb-2 scrollbar-hide">
        {choices.map((choice, i) => (
            <motion.button
                key={choice + i}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ scale: 1.05, backgroundColor: 'rgba(59, 130, 246, 0.2)' }}
                whileTap={{ scale: 0.95 }}
                onClick={() => onSelect(choice)}
                disabled={disabled}
                className={cn(
                    "px-5 py-2.5 rounded-2xl text-sm font-bold transition-all whitespace-nowrap",
                    "bg-blue-600/10 text-blue-400 border border-blue-500/20 hover:border-blue-500/50",
                    "disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                )}
            >
                {choice}
            </motion.button>
        ))}
    </div>
);

/** Course Card */
export const CourseCard = ({ course }: { course: Course }) => (
    <motion.div
        layout
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="group relative flex flex-col bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl overflow-hidden min-w-[280px] max-w-[320px] p-4 shadow-lg hover:scale-[1.02] transition-all cursor-pointer"
    >
        <div className="flex items-start justify-between mb-3">
            <div className="p-2 bg-indigo-500/20 rounded-xl text-indigo-300">
                <GraduationCap className="w-5 h-5" />
            </div>
            <span className="text-[10px] uppercase tracking-wider font-bold bg-white/5 px-2 py-1 rounded-md text-slate-300 border border-white/10">
                {course.level}
            </span>
        </div>

        <h3 className="font-bold text-lg mb-1 leading-tight text-slate-100 group-hover:text-indigo-400 transition-colors">
            {course.title}
        </h3>
        <p className="text-xs text-slate-400 mb-2">{course.instructor} • {course.category}</p>

        {course.why_recommended && (
            <div className="mt-auto pt-3 border-t border-white/5">
                <p className="text-[11px] text-indigo-300/80 italic">
                    <Sparkles className="w-3 h-3 inline-block ml-1" />
                    {course.why_recommended}
                </p>
            </div>
        )}
    </motion.div>
);

/** Learning Plan Accordion */
export const PlanAccordion = ({ plan }: { plan: LearningPlan }) => {
    const [expandedIndex, setExpandedIndex] = useState<number>(0);

    return (
        <div className="space-y-3 mt-4 w-full">
            <div className="flex items-center gap-2 mb-4">
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                    <Map className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-xl">{plan.topic} Plan</h3>
                <span className="text-xs bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded-full border border-indigo-500/20">
                    {plan.duration} • {plan.time_per_day}/day
                </span>
            </div>

            {plan.schedule.map((item, i) => (
                <motion.div
                    key={i}
                    className="glass rounded-xl overflow-hidden"
                >
                    <button
                        onClick={() => setExpandedIndex(expandedIndex === i ? -1 : i)}
                        className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <span className="w-8 h-8 flex items-center justify-center rounded-full bg-slate-800 text-xs font-bold ring-1 ring-white/10">
                                {i + 1}
                            </span>
                            <span className="font-semibold">{item.day_or_week}</span>
                        </div>
                        <ChevronDown className={cn("w-5 h-5 transition-transform", expandedIndex === i && "rotate-180")} />
                    </button>

                    <AnimatePresence>
                        {expandedIndex === i && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="px-4 pb-4"
                            >
                                <div className="space-y-3 pt-2">
                                    <div>
                                        <h4 className="text-[10px] text-slate-500 uppercase font-bold mb-2">Topics</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {item.topics.map((t, idx) => (
                                                <span key={idx} className="text-xs bg-slate-800 px-2 py-1 rounded border border-white/5">{t}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <h4 className="text-[10px] text-slate-500 uppercase font-bold mb-2">Tasks</h4>
                                        <ul className="space-y-1.5">
                                            {item.tasks.map((t, idx) => (
                                                <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                                                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                                                    {t}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>
            ))}
        </div>
    );
};

function MessageBubble({
    msg,
    onChoiceSelect,
    isLoading,
    isLatestBotMessage
}: {
    msg: Message,
    onChoiceSelect: (c: string) => void,
    isLoading: boolean,
    isLatestBotMessage?: boolean
}) {
    const isBot = msg.type === 'bot';

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className={cn(
                "flex w-full",
                isBot ? "justify-start" : "justify-end"
            )}
        >
            <div className={cn(
                "flex gap-4 max-w-[85%]",
                isBot ? "flex-row" : "flex-row-reverse"
            )}>
                <div className={cn(
                    "w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 border border-white/10 shadow-lg",
                    isBot ? "bg-slate-800" : "bg-blue-600"
                )}>
                    {isBot ? <Bot className="w-5 h-5 text-blue-400" /> : <User className="w-5 h-5 text-white" />}
                </div>

                <div className="flex flex-col gap-3">
                    <div className={cn(
                        "p-4 rounded-[20px] shadow-xl",
                        isBot ? "glass-card text-slate-200 rounded-tr-none" : "bg-blue-600 text-white rounded-tl-none ring-1 ring-blue-500/50"
                    )}>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    </div>

                    {/* RICH DATA */}
                    {isBot && msg.data && (
                        <div className="space-y-4">
                            {/* Choices - ONLY IF LATEST */}
                            {msg.data.ask && isLatestBotMessage && (
                                <ChoicesPanel
                                    choices={msg.data.ask.choices}
                                    onSelect={onChoiceSelect}
                                    disabled={isLoading}
                                />
                            )}

                            {/* Courses */}
                            {msg.data.courses && msg.data.courses.length > 0 && (
                                <div className="flex flex-col gap-3">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest pl-2">
                                        <Sparkles className="w-3 h-3 text-blue-400" />
                                        Recommended Courses
                                    </div>
                                    <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide -mx-2 px-2">
                                        {msg.data.courses.map((course, idx) => (
                                            <CourseCard key={idx} course={course} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Learning Plan */}
                            {msg.data.learning_plan && (
                                <PlanAccordion plan={msg.data.learning_plan} />
                            )}
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

export { MessageBubble };
