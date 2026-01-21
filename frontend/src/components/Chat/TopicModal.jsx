import React, { useState } from 'react';

const TOPICS = [
    "Programming",
    "Data Analysis",
    "Databases / SQL",
    "Excel / Power BI",
    "Soft Skills",
    "Digital Marketing"
];

const TopicModal = ({ isOpen, onClose, onSelect }) => {
    const [customTopic, setCustomTopic] = useState("");

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-bg-primary rounded-xl shadow-2xl border border-border w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200 p-6">
                <h3 className="text-xl font-bold mb-4 text-text-primary">
                    تحب أحدد مستواك في إيه؟
                </h3>

                <div className="grid grid-cols-2 gap-3 mb-4">
                    {TOPICS.map((topic) => (
                        <button
                            key={topic}
                            onClick={() => onSelect(topic)}
                            className="p-3 rounded-lg border border-border hover:bg-bg-hover transition-colors text-sm text-center font-medium"
                        >
                            {topic}
                        </button>
                    ))}
                </div>

                <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                        <span className="w-full border-t border-border" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                        <span className="bg-bg-primary px-2 text-text-secondary">
                            أو مجال آخر
                        </span>
                    </div>
                </div>

                <div className="mt-4 flex gap-2">
                    <input
                        type="text"
                        value={customTopic}
                        onChange={(e) => setCustomTopic(e.target.value)}
                        placeholder="اكتب المجال هنا..."
                        className="flex-1 p-2 rounded-lg border border-border bg-bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                        dir="auto"
                    />
                    <button
                        onClick={() => customTopic.trim() && onSelect(customTopic)}
                        disabled={!customTopic.trim()}
                        className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:opacity-50 font-medium text-sm transition-colors"
                    >
                        ابدأ
                    </button>
                </div>

                <button
                    onClick={onClose}
                    className="mt-4 w-full text-center text-xs text-text-secondary hover:text-text-primary underline"
                >
                    إلغاء
                </button>
            </div>
        </div>
    );
};

export default TopicModal;
