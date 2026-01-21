import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Calendar } from 'lucide-react';

const StudyPlan = ({ plan }) => {
    if (!plan || plan.length === 0) return null;

    return (
        <div className="mt-4 mb-6 w-full max-w-lg">
            <h3 className="text-sm font-medium text-accent mb-4 flex items-center gap-2">
                <Calendar size={14} />
                Your Study Plan
            </h3>

            <div className="relative border-l border-white/10 ml-3 space-y-6">
                {plan.map((week, index) => (
                    <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.15 }}
                        className="pl-6 relative"
                    >
                        {/* Dot */}
                        <div className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-surface border border-accent ring-4 ring-surface" />

                        <div className="bg-surface/50 border border-white/5 rounded-lg p-3">
                            <div className="flex justify-between mb-1">
                                <span className="text-xs font-semibold text-accent">Week {week.week}</span>
                                <span className="text-[10px] text-secondary/50 uppercase tracking-wider">{week.focus}</span>
                            </div>

                            <ul className="space-y-1.5 mt-2">
                                {week.tasks.map((task, i) => (
                                    <li key={i} className="flex items-start gap-2 text-xs text-secondary">
                                        <div className="mt-0.5 min-w-[12px]">
                                            <Circle size={8} className="text-secondary/30 mt-1" />
                                        </div>
                                        <span>{task}</span>
                                    </li>
                                ))}
                            </ul>

                            {week.milestone && (
                                <div className="mt-3 pt-2 border-t border-white/5 flex items-center gap-2 text-[10px] text-green-400">
                                    <CheckCircle2 size={10} />
                                    <span>Milestone: {week.milestone}</span>
                                </div>
                            )}
                        </div>
                    </motion.div>
                ))}
            </div>
        </div>
    );
};

export default StudyPlan;
