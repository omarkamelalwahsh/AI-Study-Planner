import { useState } from 'react'
import { Message } from '../types/chat'

interface MessageBubbleProps {
    message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.type === 'user'
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(message.content)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch (err) {
            console.error('Failed to copy:', err)
        }
    }

    return (
        <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs shrink-0 ${isUser ? 'bg-purple-600' : 'bg-blue-600'}`}>
                {isUser ? '👤' : 'AI'}
            </div>
            <div className={`flex flex-col max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
                <div className={`p-4 rounded-2xl relative group border ${isUser
                        ? 'bg-purple-600/10 border-purple-500/20 rounded-tr-none text-right'
                        : 'bg-white/5 border-white/10 rounded-tl-none text-left'
                    }`}>
                    <div className="text-sm md:text-base leading-relaxed whitespace-pre-wrap">
                        {message.content}
                    </div>

                    <button
                        className={`absolute top-2 ${isUser ? '-left-8' : '-right-8'} p-1.5 rounded-lg bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity text-xs text-gray-400 hover:text-white`}
                        onClick={handleCopy}
                        title={copied ? 'تم النسخ!' : 'نسخ'}
                    >
                        {copied ? '✓' : '📋'}
                    </button>
                </div>

                {message.data?.intent && !isUser && (
                    <span className="mt-2 text-[10px] text-gray-500 uppercase tracking-widest pl-2">
                        Intent: {message.data.intent}
                    </span>
                )}
            </div>
        </div>
    )
}
