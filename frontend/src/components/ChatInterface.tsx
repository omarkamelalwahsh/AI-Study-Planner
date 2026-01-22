import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../services/api'
import CourseCard from './CourseCard'
import MessageBubble from './MessageBubble'

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    courses?: any[];
    intent?: string;
}

export default function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [sessionId, setSessionId] = useState<string | undefined>()
    const [error, setError] = useState<string | null>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!input.trim() || loading) return

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input.trim(),
        }

        setMessages((prev) => [...prev, userMessage])
        setInput('')
        setLoading(true)
        setError(null)

        try {
            const response = await sendMessage(input.trim(), sessionId)

            // Store session ID for continuity
            if (!sessionId) {
                setSessionId(response.session_id)
            }

            const assistantMessage: Message = {
                id: response.request_id,
                role: 'assistant',
                content: response.answer,
                courses: response.courses,
                intent: response.intent,
            }

            setMessages((prev) => [...prev, assistantMessage])
        } catch (err: any) {
            setError(err.message || 'خطأ في الاتصال')
            console.error('Chat error:', err)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="chat-interface">
            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="welcome-message">
                        <h2>مرحباً! 👋</h2>
                        <p>أنا مساعدك الذكي للتوجيه المهني واختيار الكورسات</p>
                        <div className="suggestions">
                            <button onClick={() => setInput('عاوز أتعلم Python')}>
                                عاوز أتعلم Python
                            </button>
                            <button onClick={() => setInput('من بيشرح JavaScript?')}>
                                من بيشرح JavaScript?
                            </button>
                            <button onClick={() => setInput('عايز أبقى Data Scientist')}>
                                عايز أبقى Data Scientist
                            </button>
                        </div>
                    </div>
                )}

                {messages.map((msg) => (
                    <div key={msg.id}>
                        <MessageBubble message={msg} />
                        {msg.courses && msg.courses.length > 0 && (
                            <div className="courses-grid">
                                {msg.courses.map((course) => (
                                    <CourseCard key={course.id} course={course} />
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="loading-indicator">
                        <div className="spinner"></div>
                        <span>جاري التفكير...</span>
                    </div>
                )}

                {error && (
                    <div className="error-message">
                        <span>⚠️ {error}</span>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-form" onSubmit={handleSubmit}>
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="اكتب سؤالك هنا..."
                    disabled={loading}
                    maxLength={500}
                />
                <button type="submit" disabled={loading || !input.trim()}>
                    {loading ? '...' : 'إرسال'}
                </button>
            </form>
        </div>
    )
}
