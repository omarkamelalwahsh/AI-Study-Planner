import React from "react";
import { User, Copy, ThumbsUp, ThumbsDown } from "lucide-react";
import CourseCard from "../CourseCard";
import StudyPlan from "../StudyPlan";

const MessageBubble = ({ message }) => {
    // message shape from Chat Store:
    // { role: "user" | "assistant", content: string, courses?: [], study_plan?: [] }
    const role = message?.role || "user";
    const content = typeof message?.content === "string" ? message.content : String(message?.content ?? "");
    const isUser = role === "user";

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(content);
        } catch (e) {
            console.error("Copy failed:", e);
        }
    };

    return (
        <div
            className={`group w-full text-text-primary border-b border-black/5 dark:border-white/5 ${isUser ? "bg-bg-primary" : "bg-bg-surface/50"
                }`}
        >
            <div className="text-base gap-4 md:gap-6 md:max-w-2xl lg:max-w-[38rem] xl:max-w-3xl p-4 md:py-6 flex lg:px-0 m-auto">
                {/* Avatar Column */}
                <div className="flex-shrink-0 flex flex-col relative items-end">
                    <div className="relative h-7 w-7 p-1 rounded-sm text-white flex items-center justify-center bg-black/10 dark:bg-white/10">
                        {isUser ? (
                            <User size={16} className="text-text-secondary" />
                        ) : (
                            <div className="w-4 h-4 rounded-full bg-accent"></div>
                        )}
                    </div>
                </div>

                {/* Content Column */}
                <div className="relative flex-1 overflow-hidden">
                    {/* Name */}
                    <div className="font-semibold text-sm mb-1 opacity-90">{isUser ? "You" : "Assistant"}</div>

                    {/* Message Body */}
                    <div className="prose prose-sm dark:prose-invert max-w-none break-words whitespace-pre-wrap leading-7">
                        {content}
                    </div>

                    {/* Courses Grid */}
                    {message.courses && message.courses.length > 0 && (
                        <div className="mt-4 grid grid-cols-1 gap-2 w-full min-w-[300px]">
                            {message.courses.map((course, idx) => (
                                <CourseCard key={idx} course={course} index={idx} />
                            ))}
                        </div>
                    )}

                    {/* Study Plan */}
                    {message.study_plan && message.study_plan.length > 0 && (
                        <StudyPlan plan={message.study_plan} />
                    )}

                    {/* Actions Footer (Assistant Only) */}
                    {!isUser && (
                        <div className="flex items-center gap-2 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                                onClick={handleCopy}
                                className="p-1 rounded-md hover:bg-bg-hover text-text-secondary transition-colors"
                                title="Copy"
                            >
                                <Copy size={14} />
                            </button>
                            <button className="p-1 rounded-md hover:bg-bg-hover text-text-secondary transition-colors" title="Good response">
                                <ThumbsUp size={14} />
                            </button>
                            <button className="p-1 rounded-md hover:bg-bg-hover text-text-secondary transition-colors" title="Bad response">
                                <ThumbsDown size={14} />
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MessageBubble;
