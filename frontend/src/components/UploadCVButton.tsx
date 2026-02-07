"use client";

import { useRef } from "react";
import { Paperclip } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8001";

interface UploadCVButtonProps {
    sessionId: string;
    onBotReply: (data: any) => void;
    onUploadStart?: (fileName: string) => void;
    isLoading?: boolean;
}


export function UploadCVButton({ sessionId, onBotReply, onUploadStart, isLoading }: UploadCVButtonProps) {
    const fileRef = useRef<HTMLInputElement | null>(null);

    const openPicker = () => fileRef.current?.click();

    const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (onUploadStart) {
            onUploadStart(file.name);
        }

        const form = new FormData();

        form.append("file", file);
        form.append("session_id", sessionId);

        try {
            const res = await fetch(`${API_BASE}/upload-cv`, {
                method: "POST",
                body: form,
            });

            if (!res.ok) {
                throw new Error("Upload failed");
            }

            const data = await res.json();
            onBotReply(data);
        } catch (error) {
            console.error("Upload error:", error);
            // Handle error (maybe show a toast or alert)
        } finally {
            if (fileRef.current) {
                fileRef.current.value = "";
            }
        }
    };

    return (
        <>
            <button
                type="button"
                onClick={openPicker}
                disabled={isLoading}
                className="p-2 hover:bg-white/5 rounded-full text-slate-400 transition-colors disabled:opacity-50"
                title="رفع السيرة الذاتية"
            >
                <Paperclip className="w-5 h-5" />
            </button>

            <input
                ref={fileRef}
                type="file"
                accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                className="hidden"
                onChange={onPickFile}
            />
        </>
    );
}
