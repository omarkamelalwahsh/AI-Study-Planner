import React, { useState, useRef, useEffect, useCallback } from 'react'
import { sendMessage, uploadCV, fetchCourseDetails } from '../services/api'
import { useStore } from '../store/store'
import ChatInput from './ChatInput'
import CourseCard from './CourseCard'
import MessageBubble from './MessageBubble'
import { CourseModal } from './CourseModal'
import { ChatResponse, Message, Course } from '../types/chat'

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
    const [sessions, setSessions] = useState<any[]>([])
    const [showSessions, setShowSessions] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)

    const [selectedCourse, setSelectedCourse] = useState<Course | null>(null)
    const [isModalOpen, setIsModalOpen] = useState(false)

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages, typingText])

    // Typing animation
    const animateTyping = useCallback((fullText: string, onComplete: () => void) => {
        setIsTyping(true)
        setTypingText('')
        let index = 0
        const chunkSize = 4

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
        }, 20)

        return () => clearInterval(interval)
    }, [])

    const handleCourseClick = async (course: Course) => {
        if (!course.description_full) {
            try {
                const fullDetails = await fetchCourseDetails(course.course_id);
                setSelectedCourse(fullDetails);
            } catch (e) {
                setSelectedCourse(course);
            }
        } else {
            setSelectedCourse(course);
        }
        setIsModalOpen(true);
    };

    const handleBotReply = (response: ChatResponse) => {
        if (!sessionId && response.session_id) {
            setSessionId(response.session_id);
        }

        const assistantMessage: Message = {
            id: response.request_id || Date.now().toString(),
            type: 'bot',
            content: response.answer,
            timestamp: new Date(),
            data: response
        };

        addMessage(assistantMessage);
    };

    const handleUploadStart = (fileName: string) => {
        const userMsg: Message = {
            id: Date.now().toString(),
            type: 'user',
            content: `📄 Uploading CV: ${fileName}...`,
            timestamp: new Date()
        }
        addMessage(userMsg);
        setLoading(true);
    };

    const handleSubmit = async (text?: string) => {
        const messageText = (typeof text === 'string' ? text : input).trim();
        if (!messageText || isLoading) return

        const userMessage: Message = {
            id: Date.now().toString(),
            type: 'user',
            content: messageText,
            timestamp: new Date()
        }

        addMessage(userMessage)
        setInput('')
        setLoading(true)
        setError(null)

        try {
            const response = await sendMessage(messageText, sessionId)
            if (!sessionId) setSessionId(response.session_id)

            const assistantMessage: Message = {
                id: response.request_id || Date.now().toString(),
                type: 'bot',
                content: response.answer,
                timestamp: new Date(),
                data: response
            }

            animateTyping(response.answer, () => {
                addMessage(assistantMessage)
            })
        } catch (err: any) {
            setError(err.message || 'خطأ في الاتصال')
        } finally {
            setLoading(false)
        }
    }

    const handleUploadCV = async (file: File) => {
        handleUploadStart(file.name);
        try {
            const response = await uploadCV(file, sessionId);
            if (!sessionId) setSessionId(response.session_id);

            const assistantMessage: Message = {
                id: response.request_id || Date.now().toString(),
                type: 'bot',
                content: response.answer,
                timestamp: new Date(),
                data: response
            };
            addMessage(assistantMessage);
        } catch (err: any) {
            setError(err.message || 'فشل رفع الملف');
        } finally {
            setLoading(false);
        }
    }

    const handleNewChat = () => {
        clearMessages()
        setSessionId(undefined)
        setError(null)
    }

    return (
        <div className="flex flex-col h-screen bg-[#0a0a0b] text-white">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                        <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent italic">Zedny AI</h2>
                        <p className="text-gray-400">مساعدك المهني الذكي. ابدأ بسؤالي عن أي مهارة أو ارفع الـ CV بتاعك.</p>
                    </div>
                )}

                {messages.map((msg: Message) => (
                    <div key={msg.id} className="flex flex-col">
                        <MessageBubble message={msg} />

                        {msg.data?.next_actions && msg.data.next_actions.length > 0 && (
                            <div className="flex flex-wrap gap-2 my-4 ml-12">
                                {msg.data.next_actions.map((action, idx) => (
                                    <button
                                        key={idx}
                                        className="px-4 py-2 rounded-full border border-blue-500/30 bg-blue-500/5 text-blue-300 hover:bg-blue-500/20 transition-all text-sm"
                                        onClick={() => handleSubmit(action)}
                                    >
                                        {action}
                                    </button>
                                ))}
                            </div>
                        )}

                        {msg.data?.courses && msg.data.courses.length > 0 && (
                            <div className="ml-12 my-4 space-y-4">
                                <h3 className="text-lg font-bold">🌟 ترشيحات مختارة:</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {msg.data.courses.map((course) => (
                                        <CourseCard key={course.course_id} course={course} onClick={handleCourseClick} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {msg.data?.categories && msg.data.categories.length > 0 && (
                            <div className="flex flex-wrap gap-2 my-4 ml-12">
                                {msg.data.categories.map((cat, idx) => (
                                    <button
                                        key={idx}
                                        className="px-3 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/5 text-purple-300 hover:bg-purple-500/20 transition-all text-sm"
                                        onClick={() => handleSubmit(cat)}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                ))}

                {isTyping && (
                    <div className="flex gap-4 ml-2">
                        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs">AI</div>
                        <div className="bg-white/5 p-4 rounded-2xl rounded-tl-none border border-white/10 max-w-[80%]">
                            <p>{typingText}<span className="animate-pulse">|</span></p>
                        </div>
                    </div>
                )}

                {isLoading && !isTyping && (
                    <div className="flex items-center gap-2 text-gray-400 ml-12 italic text-sm">
                        <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
                        <span>جاري التفكير...</span>
                    </div>
                )}

                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-xl text-red-400 mx-12">
                        ⚠️ {error}
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <ChatInput
                value={input}
                onChange={setInput}
                onSend={handleSubmit}
                isLoading={isLoading}
                onUploadCV={handleUploadCV}
            />

            {isModalOpen && selectedCourse && (
                <CourseModal
                    course={selectedCourse}
                    onClose={() => setIsModalOpen(false)}
                />
            )}
        </div>
    )
}
