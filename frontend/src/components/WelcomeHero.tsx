"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Compass, Zap, BookOpen } from 'lucide-react';

interface WelcomeHeroProps {
    onSelectPrompt: (prompt: string) => void;
}

export default function WelcomeHero({ onSelectPrompt }: WelcomeHeroProps) {
    const prompts = [
        { text: "عاوز أبدأ أتعلم Marketing وتايه", icon: Compass },
        { text: "ازاي أطور نفسي في الـ Data Analysis؟", icon: Zap },
        { text: "ممكن تعملي خطة مذاكرة لـ React؟", icon: BookOpen },
    ];

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.05, filter: "blur(10px)" }}
            transition={{ duration: 0.5 }}
            className="flex-1 flex flex-col items-center justify-center p-8 text-center"
        >
            {/* LOGO & HERO TEXT */}
            <div className="relative mb-8 group cursor-default">
                <div className="absolute -inset-8 bg-blue-500/20 rounded-full blur-3xl opacity-50 group-hover:opacity-100 transition-opacity duration-1000 animate-pulse" />
                <div className="relative w-24 h-24 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-3xl flex items-center justify-center shadow-2xl shadow-blue-500/40 border border-white/20 transform group-hover:rotate-6 transition-transform duration-500">
                    <Sparkles className="w-12 h-12 text-white" />
                </div>
            </div>

            <h1 className="text-4xl md:text-5xl font-black mb-6 tracking-tight">
                Career Copilot <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">Zedny</span>
            </h1>

            <p className="text-slate-400 max-w-lg mb-12 text-lg leading-relaxed">
                مستشارك المهني الذكي. بيساعدك تختار كاريرك بالمظبوط، وتتعلم أحسن الكورسات، وتعمل خطط مذاكرة متفصلة ليك مخصوص.
            </p>

            {/* QUICK PROMPTS */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-4xl">
                {prompts.map((p, i) => (
                    <motion.button
                        key={i}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + i * 0.1 }}
                        whileHover={{ scale: 1.03, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onSelectPrompt(p.text)}
                        className="p-5 glass-card rounded-2xl text-right flex flex-col gap-3 group border border-white/5 hover:border-blue-500/30 hover:bg-blue-600/5 transition-all shadow-lg"
                    >
                        <div className="w-10 h-10 rounded-full bg-slate-800/50 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
                            <p.icon className="w-5 h-5 text-slate-400 group-hover:text-blue-400 transition-colors" />
                        </div>
                        <span className="text-sm font-semibold text-slate-200 group-hover:text-white transition-colors leading-relaxed">
                            {p.text}
                        </span>
                    </motion.button>
                ))}
            </div>
        </motion.div>
    );
}
