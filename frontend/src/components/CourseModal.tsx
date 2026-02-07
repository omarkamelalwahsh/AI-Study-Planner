"use client";

import React from "react";
import { X, Clock, User, Folder, BarChart } from "lucide-react";

interface Course {
    course_id: string;
    title: string;
    category?: string;
    level?: string;
    instructor?: string;
    duration_hours?: number;
    description_full?: string;
    description_short?: string;
    cover?: string;
}

interface CourseModalProps {
    course: Course;
    onClose: () => void;
}

export function CourseModal({ course, onClose }: CourseModalProps) {
    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={onClose}
        >
            <div
                className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl bg-[#0B1220] border border-white/10 shadow-2xl transition-all scale-100"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header/Cover */}
                <div className="h-48 w-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 relative">
                    {course.cover && (
                        <img
                            src={course.cover}
                            alt={course.title}
                            className="w-full h-full object-cover opacity-60"
                        />
                    )}
                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 p-2 rounded-full bg-black/20 hover:bg-black/40 text-white/70 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>

                    <div className="absolute bottom-6 left-6 right-6">
                        <h2 className="text-2xl font-bold text-white leading-tight">
                            {course.title}
                        </h2>
                    </div>
                </div>

                <div className="p-8">
                    {/* Badges/Meta */}
                    <div className="flex flex-wrap gap-3 mb-8">
                        {course.category && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/5 text-sm text-slate-300">
                                <Folder className="w-4 h-4 text-indigo-400" />
                                {course.category}
                            </div>
                        )}
                        {course.level && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/5 text-sm text-slate-300">
                                <BarChart className="w-4 h-4 text-emerald-400" />
                                {course.level}
                            </div>
                        )}
                        {course.duration_hours && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/5 text-sm text-slate-300">
                                <Clock className="w-4 h-4 text-amber-400" />
                                {course.duration_hours}h
                            </div>
                        )}
                        {course.instructor && (
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/5 text-sm text-slate-300">
                                <User className="w-4 h-4 text-blue-400" />
                                {course.instructor}
                            </div>
                        )}
                    </div>

                    {/* Description */}
                    <div className="space-y-4">
                        <h3 className="text-lg font-semibold text-white/90">عن هذا الكورس</h3>
                        <p className="text-slate-300 leading-relaxed text-base">
                            {course.description_full || course.description_short || "لا يوجد وصف متاح لهذا الكورس حالياً."}
                        </p>
                    </div>

                    {/* Footer Actions */}
                    <div className="mt-10 flex justify-end">
                        <button
                            onClick={onClose}
                            className="px-6 py-2.5 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 text-white font-medium transition-all"
                        >
                            إغلاق
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
