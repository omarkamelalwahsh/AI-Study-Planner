import React, { useState, useEffect } from 'react';
import { Star, Clock, BookOpen, ChevronRight, Search, Globe, User, Play, List } from 'lucide-react';

const CourseHero = () => {
    // These would typically come from props or data
    const courseData = {
        title: "Mastering Data Analysis with Python",
        description: "Go from beginner to professional analyst. Learn Pandas, NumPy, visualization, and statistical analysis with real-world projects.",
        rating: 4.8,
        reviews: "2.4k",
        level: "Intermediate",
        instructor: "Ahmed Hassan",
        duration: "12h 30m"
    };

    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        setIsLoaded(true);
    }, []);

    return (
        <div className="relative w-full min-h-screen bg-[#0f0f0f] text-white font-sans overflow-x-hidden">
            {/* Navbar */}
            <nav className="fixed top-0 w-full z-50 flex items-center justify-between px-6 py-4 bg-gradient-to-b from-black/80 to-transparent">
                <div className="flex items-center gap-8">
                    <div className="text-red-600 font-bold text-2xl tracking-tight">ZEDNY</div>
                    <div className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-300">
                        <a href="#" className="hover:text-white transition-colors">Dashboard</a>
                        <a href="#" className="text-white">Content Catalogue</a>
                        <a href="#" className="hover:text-white transition-colors">Assignments</a>
                        <a href="#" className="hover:text-white transition-colors">Certificates</a>
                    </div>
                </div>
                <div className="flex items-center gap-4 text-gray-300">
                    <Search className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
                    <Globe className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
                    <User className="w-5 h-5 cursor-pointer hover:text-white transition-colors" />
                </div>
            </nav>

            {/* Hero Section */}
            <div className="relative w-full h-[85vh]">
                {/* Background Image */}
                <div
                    className="absolute inset-0 bg-cover bg-center bg-no-repeat"
                    style={{
                        backgroundImage: 'url("https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2070&auto=format&fit=crop")',
                    }}
                >
                    {/* Overlay Gradient */}
                    <div className="absolute inset-0 bg-gradient-to-r from-black via-black/60 to-transparent"></div>
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0f0f0f] via-transparent to-black/40"></div>
                </div>

                {/* Content */}
                <div className={`relative h-full flex items-center px-6 md:px-16 pt-20 transition-opacity duration-1000 ${isLoaded ? 'opacity-100' : 'opacity-0'}`}>
                    <div className="max-w-2xl space-y-6">
                        {/* Tags */}
                        <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wider text-green-400">
                            <span className="bg-green-500/10 px-2 py-1 rounded">New Release</span>
                            <span className="text-gray-400">•</span>
                            <span className="text-gray-300">{courseData.duration}</span>
                        </div>

                        {/* Title */}
                        <h1 className="text-5xl md:text-6xl font-bold leading-tight tracking-tight text-white drop-shadow-lg">
                            {courseData.title}
                        </h1>

                        {/* Description */}
                        <p className="text-lg text-gray-300 line-clamp-3 leading-relaxed max-w-xl">
                            {courseData.description}
                        </p>

                        {/* Metadata */}
                        <div className="flex items-center gap-6 text-sm font-medium text-gray-400">
                            <div className="flex items-center gap-1 text-white">
                                <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                                <span>{courseData.rating}</span>
                                <span className="text-gray-500">({courseData.reviews})</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <BookOpen className="w-4 h-4" />
                                <span>{courseData.level}</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <User className="w-4 h-4" />
                                <span>{courseData.instructor}</span>
                            </div>
                        </div>

                        {/* CTAs */}
                        <div className="flex items-center gap-4 pt-4">
                            <button className="flex items-center gap-2 bg-white text-black px-8 py-3.5 rounded-md font-bold hover:bg-gray-200 transition-colors transform hover:scale-[1.02] active:scale-95">
                                <Play className="w-5 h-5 fill-black" />
                                Start Learning
                            </button>
                            <button className="flex items-center gap-2 bg-white/10 text-white px-8 py-3.5 rounded-md font-bold border border-white/20 hover:bg-white/20 transition-colors backdrop-blur-sm">
                                <List className="w-5 h-5" />
                                My List
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CourseHero;
