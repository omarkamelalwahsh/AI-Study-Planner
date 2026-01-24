interface Course {
    course_id: string;
    id?: string;
    title: string;
    level?: string;
    category?: string;
    instructor?: string;
    duration_hours?: number;
    description?: string;
    reason?: string;
}

interface CourseCardProps {
    course: Course;
}

export default function CourseCard({ course }: CourseCardProps) {
    return (
        <div className="course-card">
            <div className="course-header">
                <h3 className="course-title">{course.title}</h3>
                {course.level && (
                    <span className={`level-badge level-${course.level.toLowerCase()}`}>
                        {course.level}
                    </span>
                )}
            </div>

            <div className="course-details">
                {course.category && (
                    <div className="course-detail">
                        <span className="icon">📁</span>
                        <span>{course.category}</span>
                    </div>
                )}

                {course.instructor && (
                    <div className="course-detail">
                        <span className="icon">👨‍🏫</span>
                        <span>{course.instructor}</span>
                    </div>
                )}

                {course.duration_hours && course.duration_hours > 0 && (
                    <div className="course-detail">
                        <span className="icon">⏱️</span>
                        <span>{course.duration_hours} ساعة</span>
                    </div>
                )}
            </div>

            {course.reason && (
                <div className="course-reason">
                    <strong>💡 لماذا أرشح لك هذا الكورس:</strong> {course.reason}
                </div>
            )}

            {course.description && (
                <p className="course-description">{course.description}</p>
            )}
        </div>
    )
}
