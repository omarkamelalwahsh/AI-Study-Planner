import React, { useState } from 'react';
import { Menu, Zap, Bell, ChevronDown } from 'lucide-react';
import Sidebar from './Sidebar';
import { motion } from 'framer-motion';

const Layout = ({ chat }) => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    return (
        <div className="flex h-screen bg-background text-primary font-sans overflow-hidden selection:bg-accent/30">

            <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

            <div className="flex-1 flex flex-col min-w-0 h-full relative">

                {/* Topbar */}
                <header className="h-14 flex items-center justify-between px-4 md:px-6 border-b border-white/5 bg-[#0B0F14]/80 backdrop-blur-md z-10 mx-4 mt-2 rounded-2xl border border-white/5 shadow-lg">
                    <div className="flex items-center gap-3">
                        <button
                            className="p-2 -ml-2 text-secondary hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        >
                            <Menu size={20} />
                        </button>

                        <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-accent to-accent-hover flex items-center justify-center shadow-glow">
                                <Zap className="w-4 h-4 text-white fill-white" />
                            </div>
                            <span className="font-semibold text-base tracking-tight text-white hidden sm:block">
                                Career Copilot
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Status connection */}
                        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-full border border-emerald-500/20">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                            <span className="text-xs font-medium text-emerald-400">Connected</span>
                        </div>

                        <div className="h-6 w-px bg-white/10 mx-1 hidden sm:block"></div>

                        <button className="p-2 text-secondary hover:text-white rounded-lg hover:bg-white/5 transition-colors relative">
                            <Bell size={18} />
                            <span className="absolute top-1.5 right-2 w-2 h-2 bg-red-500 rounded-full border-2 border-[#0B0F14]"></span>
                        </button>

                        <button className="flex items-center gap-2 pl-2 pr-1 py-1 rounded-full hover:bg-white/5 border border-transparent hover:border-white/5 transition-all group">
                            <img
                                src="https://ui-avatars.com/api/?name=User&background=random"
                                alt="User"
                                className="w-7 h-7 rounded-full border border-white/10"
                            />
                            <ChevronDown size={14} className="text-secondary group-hover:text-white" />
                        </button>
                    </div>
                </header>

                {/* Main Content Area */}
                <main className="flex-1 overflow-hidden relative p-4">
                    {/* Decorative background gradients */}
                    <div className="absolute top-0 left-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl pointer-events-none -z-10" />
                    <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-600/5 rounded-full blur-3xl pointer-events-none -z-10" />

                    <div className="h-full rounded-3xl border border-white/5 bg-surface backdrop-blur-sm shadow-2xl overflow-hidden flex flex-col">
                        {chat}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default Layout;
