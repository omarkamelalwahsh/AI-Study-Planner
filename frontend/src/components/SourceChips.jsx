import React from 'react';
import { FileText } from 'lucide-react';

export default function SourceChips({ sources, onOpenPreview }) {
    return (
        <div className="mt-4 pt-3 border-t border-dashed border-border flex flex-wrap gap-2">
            {sources.map((src, idx) => (
                <button
                    key={idx}
                    onClick={() => onOpenPreview({ title: src.title, content: `Preview of ${src.title}\n\nThis is a simulated preview of the document content. In a real application, this would show the relevant text chunk extracted from the RAG system.` })}
                    className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 bg-background border border-border rounded-full text-secondary hover:text-accent hover:border-accent hover:bg-accent/5 transition-all cursor-pointer shadow-sm"
                >
                    <FileText size={12} />
                    <span className="font-medium truncate max-w-[150px]">{src.title}</span>
                </button>
            ))}
        </div>
    );
}
