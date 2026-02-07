"use client";

import React, { useMemo, useState } from "react";
import {
    BarChart3,
    Sparkles,
    Target,
    CheckCircle2,
    AlertTriangle,
    User,
    Briefcase,
    Trophy,
    FileText,
    TrendingUp,
    Check
} from "lucide-react";

/** 
 * A premium, dependency-free dashboard component using Tailwind CSS.
 * Replaces the previous version that had recharts/styled-components dependencies.
 */

// --- Simplified Card Components ---

const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`bg-[#1a1d2d] border border-white/5 rounded-2xl overflow-hidden shadow-xl ${className}`}>
        {children}
    </div>
);

const CardHeader = ({ title, description, icon: Icon, iconColor = "text-blue-400" }: { title: string; description?: string; icon?: any; iconColor?: string }) => (
    <div className="p-5 border-b border-white/5">
        <div className="flex items-center gap-3">
            {Icon && (
                <div className={`p-2 bg-white/5 rounded-lg ${iconColor}`}>
                    <Icon size={18} />
                </div>
            )}
            <div>
                <h3 className="text-white font-semibold text-base">{title}</h3>
                {description && <p className="text-slate-400 text-xs mt-0.5">{description}</p>}
            </div>
        </div>
    </div>
);

const CardContent = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`p-5 ${className}`}>
        {children}
    </div>
);

// --- Individual Visual Elements ---

const ScoreBar = ({ label, value, colorClass = "bg-blue-500" }: { label: string; value: number; colorClass?: string }) => (
    <div className="space-y-1.5">
        <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400 font-medium">{label}</span>
            <span className="text-white font-bold">{value}%</span>
        </div>
        <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
                className={`h-full transition-all duration-1000 ease-out border-r border-white/10 ${colorClass}`}
                style={{ width: `${value}%` }}
            />
        </div>
    </div>
);

const SkillBadge = ({ name, type }: { name: string; type: 'strong' | 'weak' | 'missing' }) => {
    const styles = {
        strong: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
        weak: "bg-amber-500/10 text-amber-400 border-amber-500/20",
        missing: "bg-rose-500/10 text-rose-400 border-rose-500/20"
    };

    return (
        <span className={`px-3 py-1.5 rounded-xl border text-xs font-medium ${styles[type]}`}>
            {name}
        </span>
    );
};

// --- Main Dashboard Component ---

export function CVDashboard({ data }: { data: any }) {
    const [activeTab, setActiveTab] = useState("overview");

    const d = useMemo(() => {
        if (!data) return null;
        return {
            candidate: data.candidate || { name: "المرشح", targetRole: "غير محدد", seniority: "N/A" },
            score: data.score || { overall: 0, skills: 0, experience: 0, projects: 0, marketReadiness: 0 },
            roleFit: data.roleFit || { detectedRoles: [], direction: "", summary: "" },
            skills: data.skills || { strong: [], weak: [], missing: [] },
            radar: data.radar || [],
            projects: data.projects || [],
            atsChecklist: data.atsChecklist || [],
            notes: data.notes || { strengths: "", gaps: "" },
            recommendations: data.recommendations || []
        };
    }, [data]);

    if (!d) return null;

    const overallColor = d.score.overall >= 80 ? "text-emerald-400" : d.score.overall >= 60 ? "text-amber-400" : "text-rose-400";
    const overallBg = d.score.overall >= 80 ? "bg-emerald-400/20" : d.score.overall >= 60 ? "bg-amber-400/20" : "bg-rose-400/20";

    return (
        <div className="w-full max-w-4xl transform transition-all duration-500 animate-in fade-in slide-in-from-bottom-4 mt-4" dir="ltr">
            {/* Header / Top Bar */}
            <div className="bg-[#1a1d2d]/80 backdrop-blur-xl border border-white/10 rounded-3xl p-4 mb-6 flex items-center justify-between shadow-2xl">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                        <BarChart3 className="text-white w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-white font-bold text-lg">تحليل السيرة الذاتية</h2>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-slate-400 text-[10px] font-bold uppercase tracking-widest">AI Analysis Live</span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className={`px-4 py-2 rounded-2xl flex items-center gap-2 ${overallBg}`}>
                        <Sparkles className={`w-4 h-4 ${overallColor}`} />
                        <span className={`font-bold text-xl ${overallColor}`}>{d.score.overall}</span>
                    </div>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex gap-2 p-1.5 bg-white/5 rounded-2xl mb-6 w-fit border border-white/5">
                {[
                    { id: 'overview', label: 'Overview', icon: Target },
                    { id: 'skills', label: 'Skills & Gaps', icon: Sparkles },
                    { id: 'projects', label: 'Suggested Projects', icon: Trophy }
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`
                            flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all
                            ${activeTab === tab.id
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                                : 'text-slate-400 hover:text-white hover:bg-white/5'}
                        `}
                    >
                        <tab.icon size={16} />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {activeTab === 'overview' && (
                    <>
                        <Card className="md:col-span-2">
                            <CardHeader
                                title="Candidate Fit"
                                description={d.roleFit.summary}
                                icon={User}
                                iconColor="text-indigo-400"
                            />
                            <CardContent className="grid grid-cols-2 gap-6">
                                <ScoreBar label="Skills Match" value={d.score.skills} colorClass="bg-emerald-500" />
                                <ScoreBar label="Experience" value={d.score.experience} colorClass="bg-blue-500" />
                                <ScoreBar label="Projects" value={d.score.projects} colorClass="bg-indigo-500" />
                                <ScoreBar label="Market Readiness" value={d.score.marketReadiness} colorClass="bg-amber-500" />
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader title="Quick Metrics" icon={TrendingUp} iconColor="text-emerald-400" />
                            <CardContent className="space-y-4">
                                <div className="p-4 bg-white/5 border border-white/5 rounded-2xl">
                                    <div className="text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-1">Target Role</div>
                                    <div className="text-white font-bold">{d.candidate.targetRole}</div>
                                </div>
                                <div className="p-4 bg-white/5 border border-white/5 rounded-2xl">
                                    <div className="text-slate-400 text-[10px] font-bold uppercase tracking-wider mb-1">Seniority</div>
                                    <div className="text-white font-bold">{d.candidate.seniority}</div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="md:col-span-3">
                            <CardHeader title="ATS Optimization Checklist" description="Evaluation based on algorithm-standard metrics" icon={FileText} iconColor="text-blue-400" />
                            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {d.atsChecklist.map((item: any) => (
                                    <div key={item.id} className="flex items-start gap-3 p-3 bg-white/2 rounded-xl border border-white/5">
                                        <div className={`mt-0.5 rounded-full p-1 ${item.done ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-500/20 text-slate-500'}`}>
                                            <Check size={12} className={item.done ? "visible" : "invisible"} />
                                        </div>
                                        <span className={`text-sm ${item.done ? 'text-slate-200' : 'text-slate-500'}`}>{item.text}</span>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    </>
                )}

                {activeTab === 'skills' && (
                    <>
                        <Card className="md:col-span-3">
                            <CardHeader title="Skill Keyword Analysis" description="Comparison with industry benchmarks for your target role" icon={Sparkles} iconColor="text-amber-400" />
                            <CardContent className="space-y-8">
                                <div>
                                    <h4 className="text-emerald-400 font-bold text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
                                        <CheckCircle2 size={14} /> Strong Keywords
                                    </h4>
                                    <div className="flex flex-wrap gap-2">
                                        {d.skills.strong.map((s: any, i: number) => <SkillBadge key={i} name={s.name || s} type="strong" />)}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4 border-t border-white/5">
                                    <div>
                                        <h4 className="text-rose-400 font-bold text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
                                            <AlertTriangle size={14} /> Missing Keywords (ATS Gap)
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                            {d.skills.missing.map((s: any, i: number) => <SkillBadge key={i} name={s.name || s} type="missing" />)}
                                        </div>
                                    </div>
                                    <div>
                                        <h4 className="text-amber-400 font-bold text-xs uppercase tracking-widest mb-4 flex items-center gap-2">
                                            <TrendingUp size={14} /> Growth Opps
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                            {d.skills.weak.map((s: any, i: number) => <SkillBadge key={i} name={s.name || s} type="weak" />)}
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </>
                )}

                {activeTab === 'projects' && (
                    <>
                        <div className="md:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-6">
                            {d.projects.map((proj: any, i: number) => (
                                <Card key={i}>
                                    <CardHeader title={proj.title} description={`Level: ${proj.level}`} icon={Trophy} iconColor="text-blue-400" />
                                    <CardContent>
                                        <p className="text-slate-400 text-sm leading-relaxed mb-4">{proj.description}</p>
                                        <div className="flex flex-wrap gap-2">
                                            {proj.skills?.map((s: string, j: number) => (
                                                <span key={j} className="px-2 py-1 bg-white/5 rounded-lg text-[10px] text-slate-300 font-bold border border-white/10 uppercase tracking-tighter">
                                                    {s}
                                                </span>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {/* Footer / CTA */}
            <div className="mt-8 p-6 bg-gradient-to-r from-blue-600/10 to-indigo-600/10 border border-blue-500/20 rounded-3xl">
                <h4 className="text-white font-bold mb-2 flex items-center gap-2">
                    <Sparkles className="text-blue-400" size={18} /> نصيحة الـ AI الشخصية لك
                </h4>
                <p className="text-slate-300 text-sm leading-relaxed italic">
                    {d.recommendations[0] || "استمر في تطوير مهاراتك التقنية وتركيزك على المشاريع العملية لتعزيز فرصك في السوق."}
                </p>
            </div>
        </div>
    );
}
