import { useState } from 'react'

interface SkillItem {
    name: string;
    why?: string;
    courses_count?: number;
}

interface SkillGroupProps {
    group: {
        skill_area: string;
        why_it_matters: string;
        skills: (string | SkillItem)[]; // Support both for safety
    };
    allCourses?: any[]; // Pass all courses to filter by skill later
}

export default function SkillGroupCard({ group, allCourses }: SkillGroupProps) {
    const [isExpanded, setIsExpanded] = useState(false)

    // Helper to get skill name safely
    const getSkillName = (s: string | SkillItem) => typeof s === 'string' ? s : s.name
    const getSkillWhy = (s: string | SkillItem) => typeof s === 'string' ? '' : s.why

    // Filter courses relevant to this skill group (Mock logic: matches skill area name)
    const relatedCourses = allCourses?.filter(c =>
        c.category?.toLowerCase().includes(group.skill_area.toLowerCase()) ||
        c.description?.toLowerCase().includes(group.skill_area.toLowerCase()) ||
        group.skills.some(s => c.description?.toLowerCase().includes(getSkillName(s).toLowerCase()))
    ) || []

    return (
        <>
            <div
                className={`skill-group-card ${isExpanded ? 'expanded' : ''}`}
                onClick={() => setIsExpanded(!isExpanded)}
                style={{ cursor: 'pointer', position: 'relative' }}
            >
                <div className="skill-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h4 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>{group.skill_area}</h4>
                    {group.why_it_matters && (
                        <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontStyle: 'italic' }}>
                            ℹ️ {group.why_it_matters}
                        </span>
                    )}
                </div>

                <div className="skill-tags" style={{ marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {group.skills.map((skill, idx) => {
                        const name = getSkillName(skill);
                        const why = getSkillWhy(skill);
                        return (
                            <div key={idx} className="skill-tag" title={why || name} style={{
                                display: 'flex', alignItems: 'center', gap: '4px', cursor: 'help'
                            }}>
                                {name}
                                {why && <span style={{ fontSize: '0.7rem', opacity: 0.7 }}>❓</span>}
                            </div>
                        );
                    })}
                </div>

                {relatedCourses.length > 0 && (
                    <div className="skill-courses" style={{
                        borderTop: '1px solid rgba(255,255,255,0.1)',
                        marginTop: '12px',
                        paddingTop: '12px'
                    }}>
                        <h5 style={{ margin: '0 0 12px 0', color: '#a5b4fc', fontSize: '0.9rem' }}>
                            📚 الكورسات المقترحة ({relatedCourses.length}):
                        </h5>
                        <div className="mini-courses-grid" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {relatedCourses.map((course: any) => (
                                <div key={course.course_id} className="mini-course-card" style={{
                                    background: 'rgba(0,0,0,0.2)',
                                    borderRadius: '8px',
                                    padding: '10px',
                                    border: '1px solid rgba(255,255,255,0.05)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center'
                                }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 'bold', color: '#fff', fontSize: '0.95rem' }}>
                                            {course.title}
                                        </div>
                                        {course.category && (
                                            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '2px' }}>
                                                📁 {course.category}
                                            </div>
                                        )}
                                    </div>
                                    {/* Action button or arrow if needed, for now keeping it simple as requested */}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </>
    )
}
