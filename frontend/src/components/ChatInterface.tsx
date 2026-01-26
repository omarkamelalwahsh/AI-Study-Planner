import { useState, useRef, useEffect, useCallback } from 'react'
import { sendMessage } from '../services/api'
import CourseCard from './CourseCard'
import MessageBubble from './MessageBubble'

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    courses?: any[];
    projects?: any[];
    intent?: string;
}

interface ChatSession {
    id: string;
    messages: Message[];
    createdAt: Date;
}

export default function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [sessionId, setSessionId] = useState<string | undefined>()
    const [error, setError] = useState<string | null>(null)
    const [isTyping, setIsTyping] = useState(false)
    const [typingText, setTypingText] = useState('')
    const [sessions, setSessions] = useState<ChatSession[]>([])
    const [showSessions, setShowSessions] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)

    // Load sessions from localStorage on mount
    useEffect(() => {
        const savedSessions = localStorage.getItem('chatSessions')
        if (savedSessions) {
            setSessions(JSON.parse(savedSessions))
        }
    }, [])

    // Save sessions to localStorage
    const saveSessions = useCallback((newSessions: ChatSession[]) => {
        setSessions(newSessions)
        localStorage.setItem('chatSessions', JSON.stringify(newSessions))
    }, [])

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages, typingText])

    // Auto-focus input after send
    useEffect(() => {
        if (!loading && inputRef.current) {
            inputRef.current.focus()
        }
    }, [loading])

    // Typing animation effect
    const animateTyping = useCallback((fullText: string, onComplete: () => void) => {
        setIsTyping(true)
        setTypingText('')
        let index = 0
        const chunkSize = 3 // Characters per tick for speed

        const interval = setInterval(() => {
            if (index < fullText.length) {
                setTypingText(fullText.slice(0, index + chunkSize))
                index += chunkSize
            } else {
                clearInterval(interval)
                setIsTyping(false)
                setTypingText('')
                onComplete()
            }
        }, 20) // 20ms per chunk for smooth animation

        return () => clearInterval(interval)
    }, [])

    const handleSubmit = async (e?: React.FormEvent) => {
        if (e) e.preventDefault()
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
                projects: response.projects,
                intent: response.intent,
            }

            // Animate the response
            animateTyping(response.answer, () => {
                setMessages((prev) => [...prev, assistantMessage])

                // Save to sessions
                const newSession: ChatSession = {
                    id: response.session_id,
                    messages: [...messages, userMessage, assistantMessage],
                    createdAt: new Date()
                }
                const updatedSessions = sessions.filter(s => s.id !== response.session_id)
                saveSessions([newSession, ...updatedSessions].slice(0, 10)) // Keep last 10 sessions
            })
        } catch (err: any) {
            setError(err.message || 'خطأ في الاتصال')
            console.error('Chat error:', err)
        } finally {
            setLoading(false)
        }
    }

    // Handle keyboard shortcuts: Enter to send, Shift+Enter for new line
    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    // New chat function
    const handleNewChat = () => {
        setMessages([])
        setSessionId(undefined)
        setError(null)
        setShowSessions(false)
        inputRef.current?.focus()
    }

    // Load a previous session
    const handleLoadSession = (session: ChatSession) => {
        setMessages(session.messages)
        setSessionId(session.id)
        setShowSessions(false)
    }

    // Delete a session
    const handleDeleteSession = (sessionIdToDelete: string, e: React.MouseEvent) => {
        e.stopPropagation()
        const updatedSessions = sessions.filter(s => s.id !== sessionIdToDelete)
        saveSessions(updatedSessions)

        // If deleting current session, start new chat
        if (sessionId === sessionIdToDelete) {
            handleNewChat()
        }
    }

    return (
        <div className="chat-interface">
            {/* Session controls */}
            <div className="session-controls">
                <button className="new-chat-btn" onClick={handleNewChat} title="محادثة جديدة">
                    ➕ محادثة جديدة
                </button>
                <button
                    className="sessions-btn"
                    onClick={() => setShowSessions(!showSessions)}
                    title="المحادثات السابقة"
                >
                    📋 المحادثات ({sessions.length})
                </button>
            </div>

            {/* Sessions dropdown */}
            {showSessions && sessions.length > 0 && (
                <div className="sessions-dropdown">
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className={`session-item ${session.id === sessionId ? 'active' : ''}`}
                            onClick={() => handleLoadSession(session)}
                        >
                            <span className="session-preview">
                                {session.messages[0]?.content.slice(0, 40) || 'محادثة جديدة'}...
                            </span>
                            <button
                                className="delete-session-btn"
                                onClick={(e) => handleDeleteSession(session.id, e)}
                                title="حذف المحادثة"
                            >
                                🗑️
                            </button>
                        </div>
                    ))}
                </div>
            )}

            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="welcome-message">
                        <h2>مرحباً! 👋</h2>
                        <p>أنا مساعدك الذكي للتوجيه المهني واختيار الكورسات</p>
                        <div className="suggestions">
                            <button onClick={() => setInput('عايز أبدأ مسار تعلم مهارات الـ Data Analysis')}>
                                عايز أبدأ مسار تعلم مهارات الـ Data Analysis
                            </button>
                            <button onClick={() => setInput('إيه هي الكورسات المناسبة عشان أبقى مبرمج محترف؟')}>
                                إيه هي الكورسات المناسبة عشان أبقى مبرمج محترف؟
                            </button>
                            <button onClick={() => setInput('محتاج أحسن مهارات التواصل والـ Soft Skills')}>
                                محتاج أحسن مهارات التواصل والـ Soft Skills
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
                                    <CourseCard key={course.course_id} course={course} />
                                ))}
                            </div>
                        )}
                        {msg.projects && msg.projects.length > 0 && (
                            <div className="projects-grid">
                                {msg.projects.map((project, idx) => (
                                    <div key={idx} className="project-card">
                                        <div className="project-header">
                                            <span className="project-title">🚀 {project.title}</span>
                                            <span className={`level-badge level-${project.level.toLowerCase()}`}>
                                                {project.level}
                                            </span>
                                        </div>
                                        <p className="project-description">{project.description}</p>
                                        <div className="project-skills">
                                            {project.skills.map((skill: string, sIdx: number) => (
                                                <span key={sIdx} className="project-skill-tag">{skill}</span>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {/* Typing animation */}
                {isTyping && typingText && (
                    <div className="message-bubble assistant-message typing-animation">
                        <div className="message-avatar">🤖</div>
                        <div className="message-content">
                            <div className="message-text">{typingText}<span className="cursor">|</span></div>
                        </div>
                    </div>
                )}

                {loading && !isTyping && (
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
                <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="اكتب سؤالك هنا... (Enter للإرسال، Shift+Enter لسطر جديد)"
                    disabled={loading}
                    maxLength={500}
                    rows={1}
                />
                <button type="submit" disabled={loading || !input.trim()}>
                    {loading ? (
                        <span className="spinner" style={{ width: '20px', height: '20px', borderTopColor: 'white' }}></span>
                    ) : (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    )}
                </button>
            </form>
        </div>
    )
}
