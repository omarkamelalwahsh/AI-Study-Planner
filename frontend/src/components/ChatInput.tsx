"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { Send, Zap, Paperclip } from 'lucide-react';


interface ChatInputProps {
    value: string;
    onChange: (val: string) => void;
    onSend: (text?: string) => void;
    isLoading: boolean;
    onUploadCV: (file: File) => void;
}


export default function ChatInput({ value, onChange, onSend, isLoading, onUploadCV }: ChatInputProps) {
    const fileRef = React.useRef<HTMLInputElement>(null);

    return (
        <div className="p-4 md:p-6 shrink-0 bg-white/5 backdrop-blur-xl border-t border-white/10 relative z-20">
            <div className="max-w-4xl mx-auto relative group">

                {/* Input Container */}
                <div className="relative flex items-center bg-black/20 backdrop-blur-md rounded-[24px] overflow-hidden p-2 pr-4 ring-1 ring-white/10 focus-within:ring-indigo-500/50 transition-all shadow-xl">
                    <input
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && onSend()}
                        placeholder="اسألني عن أي حاجة في الكارير..."
                        className="flex-1 bg-transparent border-none outline-none p-3 text-base md:text-sm placeholder:text-slate-500 text-slate-100 disabled:opacity-50 min-h-[50px]"
                        disabled={isLoading}
                    />

                    {/* Hidden file input */}
                    <input
                        ref={fileRef}
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) onUploadCV(f);
                            if (fileRef.current) fileRef.current.value = "";
                        }}
                    />

                    <div className="flex items-center gap-2 pl-2">
                        {/* Upload Button */}
                        <button
                            type="button"
                            onClick={() => fileRef.current?.click()}
                            disabled={isLoading}
                            className="p-2 hover:bg-white/10 rounded-full text-slate-400 transition-colors"
                            title="رفع CV"
                        >
                            <Paperclip className="w-5 h-5" />
                        </button>

                        <button className="p-2 hover:bg-white/10 rounded-full text-slate-400 hidden sm:flex">
                            <Zap className="w-5 h-5" />
                        </button>

                        {/* Send Button */}
                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => onSend()}
                            disabled={isLoading || !value.trim()}
                            className={`p-3 rounded-2xl transition-all shadow-lg flex items-center justify-center ${isLoading || !value.trim()
                                ? "bg-slate-800 text-slate-600 cursor-not-allowed"
                                : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20"
                                }`}
                        >
                            <Send className="w-5 h-5 rotate-180" />
                        </motion.button>
                    </div>

                </div>

                <p className="text-center text-[10px] text-slate-600 mt-3 font-medium uppercase tracking-[0.2rem] select-none">
                    Powered by Zedny Platform Architecture
                </p>
            </div>
        </div>
    );
}
