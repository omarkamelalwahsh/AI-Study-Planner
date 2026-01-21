import React from 'react';
import { X, FileText } from 'lucide-react';

export default function DocumentPreview({ title, content, onClose }) {
    return (
        <div className="fixed inset-0 flex items-center justify-center bg-primary/20 backdrop-blur-sm z-50 animate-fade">
            <div className="bg-surface rounded-2xl w-[600px] max-w-[90%] flex flex-col shadow-xl border border-white/50 animate-slide-up max-h-[80vh]">

                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-border bg-background/50 rounded-t-2xl">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-accent/10 rounded-lg">
                            <FileText size={18} className="text-accent" />
                        </div>
                        <h3 className="text-primary font-semibold text-base">{title}</h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 text-secondary hover:text-primary hover:bg-background rounded-lg transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto bg-surface rounded-b-2xl">
                    <div className="prose prose-sm max-w-none text-primary/80 leading-relaxed whitespace-pre-wrap">
                        {content}
                    </div>

                    {/* Highlighted snippet simulation */}
                    <div className="mt-6 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded-r-lg">
                        <p className="text-sm text-yellow-800 italic">
                            "...AI-driven career pathing algorithms utilize historical data and market trends to suggest personalized trajectories..."
                        </p>
                        <span className="text-xs text-yellow-600 font-medium mt-2 block">Matched Passage</span>
                    </div>
                </div>

            </div>
        </div>
    );
}
