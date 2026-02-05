import React from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface LayoutShellProps {
    children: React.ReactNode;
    className?: string;
}

export default function LayoutShell({ children, className }: LayoutShellProps) {
    return (
        <div
            dir="rtl"
            className={cn(
                // User-requested Premium Gradient
                "h-screen w-full bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-[#050B1E] via-[#0A1635] to-[#050B1E] text-white flex overflow-hidden",
                className
            )}
        >
            {children}
        </div>
    );
}
