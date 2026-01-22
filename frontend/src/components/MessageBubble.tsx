import { useState } from 'react'

interface Message {
    role: 'user' | 'assistant';
    content: string;
    intent?: string;
}

interface MessageBubbleProps {
    message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user'
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
        <div className={`message-bubble ${isUser ? 'user-message' : 'assistant-message'}`}>
            <div className="message-avatar">
                {isUser ? '👤' : '🤖'}
            </div>
            <div className="message-content">
                <div className="message-text">{message.content}</div>
                <div className="message-actions">
                    <button
                        className={`copy-btn ${copied ? 'copied' : ''}`}
                        onClick={handleCopy}
                        title={copied ? 'تم النسخ!' : 'نسخ'}
                    >
                        {copied ? '✓' : '📋'}
                    </button>
                    {message.intent && (
                        <span className="intent-badge">{message.intent}</span>
                    )}
                </div>
            </div>
        </div>
    )
}
