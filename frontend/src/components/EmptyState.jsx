import React from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Target, GraduationCap } from 'lucide-react';

const ActionCard = ({ icon: Icon, title, onClick, delay }) => (
    <motion.button
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay }}
        whileHover={{ scale: 1.02, backgroundColor: 'rgba(255, 255, 255, 0.1)' }}
        whileTap={{ scale: 0.98 }}
        onClick={onClick}
        className="flex flex-col items-center justify-center p-6 rounded-2xl bg-surface border border-border backdrop-blur-md shadow-card hover:shadow-glow hover:border-accent/30 transition-all group w-full text-center"
    >
        <div className="p-3 rounded-xl bg-accent/10 text-accent group-hover:bg-accent group-hover:text-black transition-colors mb-4">
            <Icon size={24} />
        </div>
        <span className="text-sm font-medium text-primary group-hover:text-white">{title}</span>
    </motion.button>
);

const EmptyState = ({ onAction }) => {
    return (
        <div className="flex flex-col items-center justify-center h-full max-w-4xl mx-auto px-6">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                className="text-center mb-12"
            >
                <div className="inline-block p-4 rounded-full bg-surface border border-border mb-6 shadow-glow">
                    <img src="/logo-icon.svg" alt="Logo" className="w-12 h-12" onError={(e) => e.target.style.display = 'none'} />
                    {/* Fallback if no logo: <Zap className="w-12 h-12 text-accent" /> */}
                </div>
                <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary mb-3">
                    How can I help you today?
                </h1>
                <p className="text-secondary text-lg">
                    I can recommend courses, assess your skills, or create a study plan.
                </p>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full">
                <ActionCard
                    icon={BookOpen}
                    title="Recommend courses"
                    delay={0.1}
                    onClick={() => onAction("Recommend courses")}
                />
                <ActionCard
                    icon={Target}
                    title="Assess my level"
                    delay={0.2}
                    onClick={() => onAction("Assess my level")}
                />
                <ActionCard
                    icon={GraduationCap}
                    title="Create study plan"
                    delay={0.3}
                    onClick={() => onAction("Create study plan")}
                />
            </div>
        </div>
    );
};

export default EmptyState;
