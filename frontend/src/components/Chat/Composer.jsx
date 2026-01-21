import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip } from 'lucide-react';

const Composer = ({ onSend, disabled }) => {
    const [input, setInput] = useState('');
    const textareaRef = useRef(null);

    const adjustHeight = () => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'; // Reset
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    };

    useEffect(() => {
        adjustHeight();
    }, [input]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    const handleSubmit = () => {
        if (!input.trim() || disabled) return;
        onSend(input);
        setInput('');
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
    };

    return (
        <div className="w-full md:max-w-2xl lg:max-w-[38rem] xl:max-w-3xl m-auto p-4  bg-gradient-to-t from-bg-primary via-bg-primary to-transparent">
            {/* Input Container */}
            <div className="relative flex items-end w-full p-3 bg-bg-surface border border-border rounded-xl shadow-sm focus-within:ring-1 focus-within:border-accent/50 focus-within:ring-accent/20 transition-all">
                {/* Attachment Icon (Visual only) */}
                {/* Attachment Icon Removed */}

                <textarea
                    ref={textareaRef}
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Send a message..."
                    className="flex-1 max-h-[200px] min-h-[24px] bg-transparent border-0 resize-none focus:ring-0 focus:outline-none py-2 text-text-primary placeholder:text-text-secondary/50"
                    style={{ overflowY: input.length > 50 ? 'auto' : 'hidden' }}
                />

                <button
                    onClick={handleSubmit}
                    disabled={!input.trim() || disabled}
                    className={`p-2 rounded-md transition-all duration-200 ml-2
                        ${input.trim()
                            ? 'bg-accent text-white shadow-glow'
                            : 'bg-transparent text-text-secondary cursor-not-allowed opacity-50'
                        }`}
                >
                    <Send size={18} />
                </button>
            </div>
            <div className="text-center text-xs text-text-secondary mt-2">
                AI can make mistakes. Consider checking important information.
            </div>
        </div>
    );
};

export default Composer;
