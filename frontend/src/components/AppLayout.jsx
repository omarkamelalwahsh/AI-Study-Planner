import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';

const AppLayout = ({ sidebar, content }) => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    return (
        <div className="flex h-screen w-full bg-bg-primary text-text-primary overflow-hidden font-sans">
            {/* Mobile Sidebar Overlay */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Sidebar Container */}
            {/* We pass the open state and close handler to the sidebar clone/wrapper if needed, 
                but here we assume 'sidebar' is an element that accepts props locally or we wrap it.
                Actually, simpler to pass props if it's a component, but since it's passed as a node, we might need to handle it.
                Typically standard 'slots' pattern. 
                
                Let's assume the parent passes the correct props, OR we enhance it here.
                Wait, standard React pattern: 
                <AppLayout sidebar={<Sidebar ... />} content={<Content ... />} />
                For the sidebar openness, the Layout controls the mobile toggle visibility, 
                but the Sidebar needs to know if it's open (for mobile class).
                
                Let's change the pattern slightly: AppLayout children?
                Or sticking to the prompt: "Provide AppLayout".
            */}

            {/* Render Sidebar with injected props if possible, or just render it */}
            {/* If sidebar is a function component we would do <Sidebar .../> but it's passed as a node most likely.
                To make it cleaner, let's assume Sidebar accepts `isOpen` and `closeSidebar` if we clone it.
             */}
            {React.cloneElement(sidebar, { isOpen: isSidebarOpen, closeSidebar: () => setIsSidebarOpen(false) })}

            {/* Main Content */}
            <main className="flex-1 flex flex-col h-full relative min-w-0">
                {/* Mobile Header for Sidebar Toggle */}
                <div className="md:hidden flex items-center p-4 border-b border-border bg-bg-primary sticky top-0 z-30">
                    <button
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        className="text-text-secondary hover:text-text-primary"
                    >
                        {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
                    </button>
                    <span className="ml-4 font-semibold text-text-primary">Chat</span>
                </div>

                {content}
            </main>
        </div>
    );
};

export default AppLayout;
