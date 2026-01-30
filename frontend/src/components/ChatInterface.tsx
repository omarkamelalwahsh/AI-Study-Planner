import { useState, useRef, useEffect, useCallback } from 'react'
import { sendMessage, uploadCV } from '../services/api'
import { useStore } from '../store/store'
import CourseCard from './CourseCard'
import MessageBubble from './MessageBubble'
import SkillGroupCard from './SkillGroupCard'

import { CVDashboard } from './CVDashboard'

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    courses?: any[];
    projects?: any[];
    skill_groups?: any[];
    learning_plan?: any;
    dashboard?: any;
    intent?: string;
}

interface ChatSession {
    id: string;
    messages: Message[];
    createdAt: Date;
}


export default function ChatInterface() {
    const { messages, isLoading, addMessage, setLoading, clearMessages } = useStore()
    const [input, setInput] = useState('')
    const [sessionId, setSessionId] = useState<string | undefined>()
    const [error, setError] = useState<string | null>(null)
    const [isTyping, setIsTyping] = useState(false)
    const [typingText, setTypingText] = useState('')
    const [sessions, setSessions] = useState<ChatSession[]>([])
    const [showSessions, setShowSessions] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

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
        if (!isLoading && inputRef.current) {
            inputRef.current.focus()
        }
    }, [isLoading])

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
        if (!input.trim() || isLoading) return

        const userMessage: Omit<Message, 'id' | 'timestamp'> = {
            role: 'user',
            content: input.trim(),
        }

        addMessage(userMessage as any)
        setInput('')
        setLoading(true)
        setError(null)

        try {
            const response = await sendMessage(input.trim(), sessionId)

            // Store session ID for continuity
            if (!sessionId) {
                setSessionId(response.session_id)
            }

            const assistantMessage: any = {
                role: 'assistant',
                content: response.answer,
                courses: response.courses,
                projects: response.projects,
                skill_groups: response.skill_groups,
                learning_plan: response.learning_plan,
                dashboard: response.dashboard,
                intent: response.intent,
            }

            // Animate the response
            animateTyping(response.answer, () => {
                const fullAssistantMsg = { ...assistantMessage, id: response.request_id }
                // We add to store manually or let store handle ID? Store handles ID.
                addMessage(assistantMessage)

                // Save to sessions (Note: We need the actual messages with IDs from store... 
                // but store updates async/sync. For simplicity, we reconstruct)
                // Actually, let's just trigger save based on store state in a useEffect or use simple reconstruction
                const newSession: ChatSession = {
                    id: response.session_id,
                    messages: [...messages, { ...userMessage, id: Date.now().toString() } as Message, fullAssistantMsg],
                    createdAt: new Date()
                }
                const updatedSessions = sessions.filter(s => s.id !== response.session_id)
                saveSessions([newSession, ...updatedSessions].slice(0, 10))
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

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        setLoading(true)
        setError(null)

        // Add optimistic user message for file upload
        const userMsg = {
            role: 'user',
            content: `📄 Uploading CV: ${file.name}...`
        }
        addMessage(userMsg as any)

        try {
            const response = await uploadCV(file, sessionId)

            if (!sessionId) {
                setSessionId(response.session_id)
            }

            const assistantMessage: any = {
                role: 'assistant',
                content: response.answer,
                courses: response.courses,
                projects: response.projects,
                skill_groups: response.skill_groups,
                learning_plan: response.learning_plan,
                dashboard: response.dashboard,
                intent: response.intent,
            }

            addMessage(assistantMessage)

            // Save to sessions
            const newSession: ChatSession = {
                id: response.session_id,
                messages: [...messages, { ...userMsg, id: Date.now().toString() } as Message, { ...assistantMessage, id: response.request_id }],
                createdAt: new Date()
            }
            const updatedSessions = sessions.filter(s => s.id !== response.session_id)
            saveSessions([newSession, ...updatedSessions].slice(0, 10))

        } catch (err: any) {
            setError(err.message || 'فشل رفع الملف')
        } finally {
            setLoading(false)
            if (fileInputRef.current) fileInputRef.current.value = ''
        }
    }

    const triggerFileUpload = () => {
        fileInputRef.current?.click()
    }

    // New chat function
    const handleNewChat = () => {
        clearMessages()
        setSessionId(undefined)
        setError(null)
        setShowSessions(false)
        inputRef.current?.focus()
    }

    // Load a previous session
    const handleLoadSession = (session: ChatSession) => {
        clearMessages()
        // Bulk add - tricky with current store action "addMessage". 
        // We'll iterate or add a "setMessages" action to store.
        // ideally add 'setMessages' to store. For now, iterate:
        session.messages.forEach(m => addMessage(m as any))

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

                {messages.map((msg: any) => (
                    <div key={msg.id}>
                        <MessageBubble message={msg} />

                        {msg.dashboard && (
                            <CVDashboard data={msg.dashboard} />
                        )}

                        {msg.skill_groups && msg.skill_groups.length > 0 && (
                            <div className="skill-groups-container">
                                <h3>📊 المهارات المطلوبة:</h3>
                                <div className="skill-groups-grid">
                                    {msg.skill_groups.map((group: any, idx: number) => (
                                        <SkillGroupCard
                                            key={idx}
                                            group={group}
                                            allCourses={msg.courses} // Pass courses to find relations
                                        />
                                    ))}
                                </div>
                            </div>
                        )}

                        {msg.courses && msg.courses.length > 0 && (!msg.skill_groups || msg.skill_groups.length === 0) && (
                            <div className="courses-section">
                                <h3>📚 كورسات مقترحة:</h3>
                                <div className="courses-grid">
                                    {msg.courses.map((course: any) => (
                                        <CourseCard key={course.course_id} course={course} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {msg.learning_plan && (
                            <div className="learning-plan-container">
                                <h3>🗺️ خطة التعلم المقترحة:</h3>
                                {msg.learning_plan.phases ? (
                                    <div className="learning-plan-phases">
                                        {msg.learning_plan.phases.map((phase: any, idx: number) => (
                                            <div key={idx} className="phase-card" style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.05)', padding: '16px', borderRadius: '8px', borderLeft: '4px solid #8b5cf6' }}>
                                                <div className="phase-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                                    <h4 style={{ margin: 0, color: '#fff' }}>{phase.title}</h4>
                                                    <span className="phase-duration" style={{ background: 'rgba(139, 92, 246, 0.2)', color: '#a78bfa', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem' }}>{phase.weeks} Weeks</span>
                                                </div>
                                                <div className="phase-skills" style={{ marginBottom: '8px' }}>
                                                    {phase.skills.map((s: string, i: number) => (
                                                        <span key={i} style={{ display: 'inline-block', background: 'rgba(59, 130, 246, 0.1)', color: '#60a5fa', fontSize: '0.8rem', padding: '2px 6px', borderRadius: '4px', marginRight: '6px', marginBottom: '4px' }}>{s}</span>
                                                    ))}
                                                </div>
                                                {phase.deliverables && phase.deliverables.length > 0 && (
                                                    <div className="phase-deliverables" style={{ fontSize: '0.9rem', color: '#cbd5e1' }}>
                                                        <strong>🎯 Deliverables:</strong>
                                                        <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px' }}>
                                                            {phase.deliverables.map((d: string, i: number) => (
                                                                <li key={i}>{d}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="learning-plan-weeks">
                                        {msg.learning_plan.schedule.map((week: any, idx: number) => (
                                            <div key={idx} className="plan-week">
                                                <div className="week-header">أسبوع {week.week}: {week.focus}</div>
                                                <div className="week-outcomes">
                                                    {week.outcomes.map((o: string, oIdx: number) => (
                                                        <div key={oIdx} className="outcome-item">✅ {o}</div>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                        {msg.projects && msg.projects.length > 0 && (
                            <div className="projects-grid">
                                {msg.projects.map((project: any, idx: number) => (
                                    <div key={idx} className="project-card">
                                        <div className="project-header">
                                            <span className="project-title">🚀 {project.title}</span>
                                            <span className={`level-badge level-${(project.difficulty || project.level || 'Beginner').toLowerCase()}`}>
                                                {project.difficulty || project.level}
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

                {isLoading && !isTyping && (
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
                    disabled={isLoading}
                    maxLength={500}
                    rows={1}
                />
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    style={{ display: 'none' }}
                    accept=".pdf,.docx,.txt"
                />
                <button
                    type="button"
                    className="upload-btn"
                    onClick={triggerFileUpload}
                    disabled={isLoading}
                    title="رفع CV (PDF/DOCX)"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '0 10px' }}
                >
                    📎
                </button>
                <button type="submit" disabled={isLoading || !input.trim()}>
                    {isLoading ? (
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
