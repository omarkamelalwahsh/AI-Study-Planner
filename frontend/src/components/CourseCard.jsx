import React from 'react';
import { Clock, BookOpen, Star, User, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const CourseCard = ({ course, index }) => {
    return (
        <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-surface border border-white/10 rounded-xl p-4 mb-3 hover:border-accent/30 transition-all group w-full max-w-sm"
        >
            <div className="flex justify-between items-start mb-2">
                <h4 className="font-medium text-primary line-clamp-2 group-hover:text-accent transition-colors">
                    {course.title}
                </h4>
                <span className={`text-[10px] px-2 py-1 rounded-full border ${course.level === 'Beginner' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                        course.level === 'Intermediate' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                            'bg-red-500/10 text-red-400 border-red-500/20'
                    }`}>
                    {course.level}
                </span>
            </div>

            <p className="text-secondary text-xs mb-3 line-clamp-2">
                {course.reason}
            </p>

            <div className="flex items-center gap-3 text-xs text-secondary/70 border-t border-white/5 pt-3">
                {course.duration_hours && (
                    <div className="flex items-center gap-1">
                        <Clock size={12} />
                        <span>{course.duration_hours}h</span>
                    </div>
                )}
                {course.instructor && (
                    <div className="flex items-center gap-1">
                        <User size={12} />
                        <span className="truncate max-w-[80px]">{course.instructor}</span>
                    </div>
                )}
                <div className="flex-1" />
                {course.score && (
                    <div className="flex items-center gap-1 text-accent">
                        <Star size={12} className="fill-accent" />
                        <span>{Math.round(course.score * 100)}%</span>
                    </div>
                )}
            </div>

            {course.missing_skills && course.missing_skills.length > 0 && (
                <div className="mt-3 pt-2 border-t border-white/5 flex gap-1 items-center text-red-400 text-[10px]">
                    <AlertCircle size={10} />
                    <span>Missing: {course.missing_skills.join(", ")}</span>
                </div>
            )}
        </motion.div>
    );
};

export default CourseCard;
