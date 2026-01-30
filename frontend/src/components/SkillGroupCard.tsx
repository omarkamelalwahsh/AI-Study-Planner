import { useState } from 'react'
import CourseCard from './CourseCard'

interface SkillGroupProps {
    group: {
        skill_area: string;
        why_it_matters: string;
        skills: string[];
    };
    allCourses?: any[]; // Pass all courses to filter by skill later
}

export default function SkillGroupCard({ group, allCourses }: SkillGroupProps) {
    const [isExpanded, setIsExpanded] = useState(false)
    const [showModal, setShowModal] = useState(false)

    // Filter courses relevant to this skill group (Mock logic: matches skill area name)
    const relatedCourses = allCourses?.filter(c =>
        c.category?.toLowerCase().includes(group.skill_area.toLowerCase()) ||
        c.description?.toLowerCase().includes(group.skill_area.toLowerCase()) ||
        group.skills.some(s => c.description?.toLowerCase().includes(s.toLowerCase()))
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
                    {relatedCourses.length > 0 && (
                        <button
                            style={{
                                background: 'rgba(99, 102, 241, 0.2)',
                                border: '1px solid rgba(99, 102, 241, 0.4)',
                                color: '#a5b4fc',
                                padding: '4px 8px',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '0.8rem'
                            }}
                            onClick={(e) => {
                                e.stopPropagation()
                                setShowModal(true)
                            }}
                        >
                            📚 {relatedCourses.length} كورسات
                        </button>
                    )}
                </div>

                <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '12px' }}>
                    {group.why_it_matters}
                </p>

                <div className="skill-tags">
                    {group.skills.map((skill, idx) => (
                        <span key={idx} className="skill-tag">
                            {skill}
                        </span>
                    ))}
                </div>
            </div>

            {/* Modal for Courses */}
            {showModal && (
                <div
                    className="modal-overlay"
                    onClick={() => setShowModal(false)}
                    style={{
                        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                        background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', zIndex: 1000,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
                    }}
                >
                    <div
                        className="modal-content"
                        onClick={e => e.stopPropagation()}
                        style={{
                            background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '16px', width: '100%', maxWidth: '500px', maxHeight: '80vh',
                            display: 'flex', flexDirection: 'column'
                        }}
                    >
                        <div className="modal-header" style={{ padding: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between' }}>
                            <h3 style={{ margin: 0, color: '#fff' }}>كورسات {group.skill_area}</h3>
                            <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
                        </div>
                        <div className="modal-body" style={{ padding: '20px', overflowY: 'auto' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {relatedCourses.map((course: any) => (
                                    <CourseCard key={course.course_id} course={course} />
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
