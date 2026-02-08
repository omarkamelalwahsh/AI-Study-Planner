"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Compass, Zap, BookOpen } from 'lucide-react';

interface WelcomeHeroProps {
    onSelectPrompt: (prompt: string) => void;
}

export default function WelcomeHero({ onSelectPrompt }: WelcomeHeroProps) {
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

            {/* QUICK PROMPTS REMOVED PER USER REQUEST */}
            <div className="hidden"></div>
        </motion.div>
    );
}
