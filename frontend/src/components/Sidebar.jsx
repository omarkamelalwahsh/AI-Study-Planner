import React from 'react';
import { Plus, MessageSquare, Trash2, Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const Sidebar = ({ chats, activeChatId, onSelectChat, onNewChat, onDeleteChat, isOpen, closeSidebar }) => {
    const { theme, setTheme } = useTheme();

    // Helper to get relative time label (optional enhancement, kept simple for now)
    const reversedChats = [...chats].reverse(); // Show newest first

    return (
        <aside
            className={`
                fixed inset-y-0 left-0 z-50 w-[260px] bg-bg-surface border-r border-border
                transform transition-transform duration-300 ease-in-out
                ${isOpen ? 'translate-x-0' : '-translate-x-full'}
                md:relative md:translate-x-0 flex flex-col
            `}
        >
            {/* New Chat Button */}
            <div className="p-3">
                <button
                    onClick={() => {
                        onNewChat();
                        if (window.innerWidth < 768) closeSidebar();
                    }}
                    className="flex items-center gap-3 w-full px-3 py-3 rounded-md border border-border hover:bg-bg-hover transition-colors text-sm text-text-primary text-left"
                >
                    <Plus size={16} />
                    <span>New chat</span>
                </button>
            </div>

            {/* Chat List */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-hide">
                <div className="text-xs font-medium text-text-secondary px-3 py-2">Restored Chats</div>
                {reversedChats.map((chat) => (
                    <div
                        key={chat.id}
                        className={`group relative flex items-center gap-3 px-3 py-3 rounded-md cursor-pointer transition-colors text-sm
                            ${chat.id === activeChatId ? 'bg-bg-hover' : 'hover:bg-bg-hover'}
                        `}
                        onClick={() => {
                            onSelectChat(chat.id);
                            if (window.innerWidth < 768) closeSidebar();
                        }}
                    >
                        <MessageSquare size={16} className="text-text-secondary shrink-0" />
                        <div className="flex-1 truncate text-text-primary pr-6">
                            {chat.title || 'New Chat'}
                        </div>

                        {/* Delete Action (visible on hover or active) */}
                        {chat.id === activeChatId && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteChat(chat.id);
                                }}
                                className="absolute right-2 text-text-secondary hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                title="Delete chat"
                            >
                                <Trash2 size={14} />
                            </button>
                        )}
                    </div>
                ))}
            </div>

            {/* Footer / Theme Toggle */}
            <div className="p-3 border-t border-border">
                <div className="flex items-center justify-between px-3 py-2 text-sm text-text-primary">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-green-500"></div>
                        <span className="text-xs font-medium">v1.0.0</span>
                    </div>
                </div>

                {/* Theme Toggle Group */}
                <div className="flex items-center gap-1 mt-2 bg-bg-hover/50 p-1 rounded-lg">
                    <button
                        onClick={() => setTheme('light')}
                        className={`flex-1 p-2 rounded-md flex justify-center transition-colors ${theme === 'light' ? 'bg-bg-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}`}
                        title="Light Mode"
                    >
                        <Sun size={16} />
                    </button>
                    <button
                        onClick={() => setTheme('system')}
                        className={`flex-1 p-2 rounded-md flex justify-center transition-colors ${theme === 'system' ? 'bg-bg-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}`}
                        title="System Default"
                    >
                        <Monitor size={16} />
                    </button>
                    <button
                        onClick={() => setTheme('dark')}
                        className={`flex-1 p-2 rounded-md flex justify-center transition-colors ${theme === 'dark' ? 'bg-bg-primary shadow-sm' : 'text-text-secondary hover:text-text-primary'}`}
                        title="Dark Mode"
                    >
                        <Moon size={16} />
                    </button>
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
