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

    return (
        <div className={`message-bubble ${isUser ? 'user-message' : 'assistant-message'}`}>
            <div className="message-avatar">
                {isUser ? '👤' : '🤖'}
            </div>
            <div className="message-content">
                <div className="message-text">{message.content}</div>
                {message.intent && (
                    <div className="message-meta">
                        <span className="intent-badge">{message.intent}</span>
                    </div>
                )}
            </div>
        </div>
    )
}
