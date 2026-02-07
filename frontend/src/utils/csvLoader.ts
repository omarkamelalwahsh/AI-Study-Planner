import fs from 'fs';
import path from 'path';
import { Course } from '@/types/chat';

const CSV_PATH = path.join(process.cwd(), '../data/courses.csv');

export function loadCourses(): Course[] {
    try {
        // Check if file exists
        if (!fs.existsSync(CSV_PATH)) {
            console.warn('Courses CSV not found at:', CSV_PATH);
            return [];
        }

        const fileContent = fs.readFileSync(CSV_PATH, 'utf-8');
        const lines = fileContent.split(/\r?\n/);
        const headers = lines[0].split(',');

        const courses: Course[] = [];

        // Basic CSV parser required to handle quoted strings containing commas
        const parseLine = (line: string): string[] => {
            const result: string[] = [];
            let current = '';
            let inQuote = false;

            for (let i = 0; i < line.length; i++) {
                const char = line[i];

                if (char === '"') {
                    inQuote = !inQuote;
                } else if (char === ',' && !inQuote) {
                    result.push(current);
                    current = '';
                } else {
                    current += char;
                }
            }
            result.push(current);
            return result;
        };

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const columns = parseLine(line);

            // Expected columns: course_id,title,category,level,duration_hours,skills,description,instructor,cover
            if (columns.length < 9) continue;

            let coverUrl = columns[8];

            // SECURITY FIX: Remove logic-exposed JWT tokens from URLs
            if (coverUrl && coverUrl.includes('?token=')) {
                coverUrl = coverUrl.split('?token=')[0];
            }

            courses.push({
                course_id: columns[0],
                title: columns[1],
                category: columns[2],
                level: columns[3],
                // duration is columns[4] -> Not in interface, ignored
                // skills is columns[5] -> Not in interface, ignored or appended to description?
                description: columns[6].replace(/^"|"$/g, ''), // Remove wrapping quotes if present
                instructor: columns[7],
                thumbnail: coverUrl
            });
        }

        return courses;
    } catch (error) {
        console.error('Failed to load courses:', error);
        return [];
    }
}
