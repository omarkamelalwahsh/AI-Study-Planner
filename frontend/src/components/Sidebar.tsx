"use client";

import React from 'react';
import { motion } from 'framer-motion';
import {
    Sparkles, PlusCircle, History, LayoutDashboard, Settings,
    LogOut, MoreHorizontal
} from 'lucide-react';

interface SidebarProps {
    onNewChat: () => void;
    isOpen: boolean;
    sessions: { id: string; title: string }[];
    onOpenSession: (id: string) => void;
    onDeleteSession: (id: string) => void;
}

export default function Sidebar({ onNewChat, isOpen, sessions, onOpenSession, onDeleteSession }: SidebarProps) {
    return (
        <motion.aside
            initial={false}
            animate={{
                width: isOpen ? 280 : 0,
                opacity: isOpen ? 1 : 0
            }}
            transition={{ type: "spring", bounce: 0, duration: 0.4 }}
            className="h-full shrink-0 flex flex-col bg-white/5 backdrop-blur-2xl border-l border-white/10 overflow-hidden relative z-40 shadow-2xl"
        >
            {/* BRAND HEADER */}
            <div className="p-6 border-b border-white/5 flex items-center justify-between shrink-0 bg-white/5">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20">
                        <Sparkles className="w-5 h-5 text-white" />
                    </div>
                    <span className="font-bold text-lg tracking-tight whitespace-nowrap">Career Copilot</span>
                </div>
            </div>

            {/* ACTION BUTTON */}
            <div className="p-4 shrink-0">
                <button
                    onClick={onNewChat}
                    className="flex items-center justify-center gap-3 w-full p-4 rounded-2xl bg-blue-600/10 text-blue-400 hover:bg-blue-600/20 transition-all border border-blue-500/20 group cursor-pointer"
                >
                    <PlusCircle className="w-5 h-5 group-hover:rotate-90 transition-transform" />
                    <span className="font-bold text-sm whitespace-nowrap">محادثة جديدة</span>
                </button>
            </div>

            {/* SCROLLABLE HISTORY */}
            <div className="flex-1 overflow-y-auto scrollbar-hide px-4 pb-4">
                <div className="text-[10px] uppercase font-black text-slate-500 px-2 mb-3 tracking-widest whitespace-nowrap">
                    المحادثات السابقة
                </div>
                <div className="space-y-2">
                    {sessions.map(s => (
                        <div
                            key={s.id}
                            onClick={() => onOpenSession(s.id)}
                            className="p-3 rounded-xl bg-white/5 border border-white/5 flex items-center justify-between cursor-pointer hover:bg-white/10 hover:border-white/10 transition-all group"
                        >
                            <div className="flex items-center gap-3 truncate">
                                <History className="w-4 h-4 text-slate-500 group-hover:text-blue-400 shrink-0" />
                                <span className="text-sm text-slate-300 truncate">{s.title}</span>
                            </div>

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteSession(s.id);
                                }}
                                className="p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded-lg text-slate-500 transition-colors opacity-0 group-hover:opacity-100"
                                title="حذف"
                            >
                                <LogOut className="w-4 h-4 rotate-90" /> {/* Using LogOut as a temporary Trash icon if not available */}
                            </button>
                        </div>
                    ))}

                    {sessions.length === 0 && (
                        <div className="text-center py-8 text-slate-600 text-xs">
                            لا يوجد محادثات سابقة
                        </div>
                    )}
                </div>
            </div>

            {/* FOOTER ACTIONS */}
            <div className="p-4 border-t border-white/5 space-y-1 shrink-0 bg-slate-950/20 backdrop-blur-sm">
                <button className="flex items-center gap-3 w-full p-3 rounded-xl hover:bg-white/5 text-slate-400 hover:text-white transition-colors">
                    <LayoutDashboard className="w-5 h-5 shrink-0" />
                    <span className="text-sm font-medium whitespace-nowrap">لوحة التحكم</span>
                </button>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400 border border-white/10">
                            ME
                        </div>
                        <div className="flex flex-col">
                            <span className="text-xs font-bold text-slate-200">User</span>
                            <span className="text-[10px] text-slate-500">Free Plan</span>
                        </div>
                    </div>
                    <button className="p-2 hover:bg-white/10 rounded-lg text-slate-400">
                        <Settings className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </motion.aside>
    );
}
