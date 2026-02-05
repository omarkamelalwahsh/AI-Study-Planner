import type { Metadata } from "next";
import { Cairo } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

const cairo = Cairo({ subsets: ["arabic", "latin"] });

export const metadata: Metadata = {
    title: "Career Copilot | Zedny",
    description: "Your modern AI-powered career assistant.",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="ar" dir="rtl">
            <body className={`${cairo.className} animated-bg text-slate-100`}>
                {children}
                <Toaster position="top-center" />
            </body>
        </html>
    );
}
