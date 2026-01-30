import React, { useMemo, useState } from "react";
import styled from "styled-components";
// Removed unused imports
import {
    BarChart3,
    Sparkles,
    Target,
    CheckCircle2,
    AlertTriangle,
} from "lucide-react";
import {
    ResponsiveContainer,
    RadarChart,
    PolarGrid,
    PolarAngleAxis,
    Radar,
    Tooltip,
    BarChart,
    CartesianGrid,
    XAxis,
    YAxis,
    Bar,
} from "recharts";

// --- Styled Components (Shim for shadcn/ui) ---

const DashboardContainer = styled.div`
  min-height: 100vh;
  background: #0f111a;
  color: #fff;
  font-family: 'Inter', sans-serif;
  direction: ltr; /* Dashboard is technical, keep LTR usually, or RTL if needed */
`;

const TopBar = styled.div`
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  background: rgba(15, 17, 26, 0.85);
  backdrop-filter: blur(10px);
  padding: 1rem;
`;

const TopBarContent = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const LogoSection = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const IconBox = styled.div`
  padding: 8px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
`;

const Card = styled.div`
  background: #1a1d2d;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  overflow: hidden;
`;

const CardHeader = styled.div`
  padding: 1.5rem 1.5rem 0.5rem;
`;

const CardContent = styled.div`
  padding: 1.5rem;
`;

const CardTitle = styled.h3`
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
  margin: 0;
`;

const CardDescription = styled.p`
  font-size: 0.875rem;
  color: #94a3b8;
  margin: 4px 0 0;
`;

const Grid = styled.div`
  display: grid;
  gap: 1.5rem;
  grid-template-columns: 1fr;
  
  @media (min-width: 1024px) {
    grid-template-columns: repeat(3, 1fr);
  }
`;

const Badge = styled.span<{ variant?: string }>`
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
  background: ${props => props.variant === "secondary" ? "rgba(255,255,255,0.1)" : "rgba(139, 92, 246, 0.2)"};
  color: ${props => props.variant === "secondary" ? "#cbd5e1" : "#a78bfa"};
  border: 1px solid ${props => props.variant === "secondary" ? "transparent" : "rgba(139, 92, 246, 0.3)"};
`;

// Removed unused Button styled component
const Button = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  background: ${props => props.className?.includes("outline") ? "transparent" : "#3b82f6"};
  color: ${props => props.className?.includes("outline") ? "#fff" : "#fff"};
  border: 1px solid ${props => props.className?.includes("outline") ? "rgba(255,255,255,0.2)" : "transparent"};

  &:hover {
    background: ${props => props.className?.includes("outline") ? "rgba(255,255,255,0.05)" : "#2563eb"};
  }
`;

const TabsList = styled.div`
  display: flex;
  gap: 8px;
  background: rgba(255,255,255,0.03);
  padding: 6px;
  border-radius: 16px;
  margin-bottom: 24px;
`;

const TabTrigger = styled.button<{ active: boolean }>`
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  background: ${props => props.active ? "#2d3748" : "transparent"};
  color: ${props => props.active ? "#fff" : "#94a3b8"};
  transition: all 0.2s;

  &:hover {
    color: #fff;
  }
`;

const ScoreRingContainer = styled.div`
  background: #1e293b;
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 16px;
  padding: 16px;
`;

const ProgressBar = styled.div`
  height: 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-top: 12px;
`;

const ProgressFill = styled.div<{ width: number; color: string }>`
  height: 100%;
  width: ${props => props.width}%;
  background-color: ${props => props.color};
  border-radius: 4px;
  transition: width 1s ease-out;
`;

// --- Components ---

function ScoreRing({ label, value }: { label: string; value: number }) {
    const color = value >= 80 ? "#10b981" : value >= 60 ? "#f59e0b" : "#ef4444";
    return (
        <ScoreRingContainer>
            <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginBottom: '8px' }}>{label}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#fff' }}>{value}</div>
            <ProgressBar>
                <ProgressFill width={value} color={color} />
            </ProgressBar>
        </ScoreRingContainer>
    );
}

function SkillPill({ name, tone }: { name: string; tone: "strong" | "weak" | "missing" }) {
    let bg = "rgba(75, 85, 99, 0.2)";
    let color = "#9ca3af";
    let border = "transparent";

    if (tone === "strong") {
        bg = "rgba(16, 185, 129, 0.1)";
        color = "#34d399";
        border = "rgba(16, 185, 129, 0.2)";
    } else if (tone === "weak") {
        bg = "rgba(245, 158, 11, 0.1)";
        color = "#fbbf24";
        border = "rgba(245, 158, 11, 0.2)";
    } else if (tone === "missing") {
        bg = "rgba(239, 68, 68, 0.1)";
        color = "#f87171";
        border = "rgba(239, 68, 68, 0.2)";
    }

    return (
        <span style={{
            display: "inline-block",
            padding: "6px 12px",
            borderRadius: "99px",
            fontSize: "0.75rem",
            background: bg,
            color: color,
            border: `1px solid ${border}`,
            marginRight: "6px",
            marginBottom: "6px"
        }}>
            {name}
        </span>
    );
}

// --- Main Component ---

export function CVDashboard({ data }: { data: any }) {
    const [activeTab, setActiveTab] = useState("skills");

    // Fallback / Demo data mapper
    // Real Data Mapping
    const dashboardData = useMemo(() => {
        if (!data) return null;

        // Return data directly as it now matches schema from backend
        return {
            candidate: data.candidate || { name: "Candidate", targetRole: "Unknown", seniority: "Unknown" },
            score: data.score || { overall: 0, skills: 0, experience: 0, projects: 0, marketReadiness: 0 },
            roleFit: data.roleFit || { detectedRoles: [], direction: "Analysis", summary: "No data available." },
            skills: data.skills || { strong: [], weak: [], missing: [] },
            radar: data.radar || [],
            projects: data.projects || [],
            atsChecklist: data.atsChecklist || [],
            notes: data.notes || { strengths: "N/A", gaps: "N/A" },
            recommendations: data.recommendations || []
        };
    }, [data]);

    const overallColor = (dashboardData?.score?.overall || 0) >= 80 ? "#34d399" : (dashboardData?.score?.overall || 0) >= 60 ? "#fbbf24" : "#f87171";

    if (!dashboardData) return null;

    return (
        <DashboardContainer>
            <TopBar>
                <TopBarContent>
                    <LogoSection>
                        <IconBox><BarChart3 size={20} color="#3b82f6" /></IconBox>
                        <div>
                            <div style={{ fontWeight: 600 }}>CV Analysis Dashboard</div>
                            <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>AI-Powered Review</div>
                        </div>
                    </LogoSection>
                    <Badge variant="secondary">Beta v1.0</Badge>
                </TopBarContent>
            </TopBar>

            <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>

                {/* Overview Cards */}
                <Grid>
                    <Card style={{ gridColumn: 'span 2' }}>
                        <CardHeader>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                                <div>
                                    <CardTitle>Analysis Overview</CardTitle>
                                    <CardDescription>{dashboardData.roleFit.summary}</CardDescription>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontSize: '3rem', fontWeight: 'bold', color: overallColor, lineHeight: 1 }}>
                                        {dashboardData.score.overall}
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Overall Score</div>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
                                <ScoreRing label="Skills Match" value={dashboardData.score.skills} />
                                <ScoreRing label="Experience" value={dashboardData.score.experience} />
                                <ScoreRing label="ATS Check" value={dashboardData.score.ats} />
                                <ScoreRing label="Readiness" value={dashboardData.score.readiness} />
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Skill Radar</CardTitle>
                            <CardDescription>Performance across dimensions</CardDescription>
                        </CardHeader>
                        <CardContent style={{ height: '300px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={dashboardData.radar}>
                                    <PolarGrid stroke="rgba(255,255,255,0.1)" />
                                    <PolarAngleAxis dataKey="area" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                                    <Radar name="Score" dataKey="value" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.3} />
                                    <Tooltip
                                        contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                        itemStyle={{ color: '#fff' }}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Tab Navigation */}
                <div style={{ marginTop: '32px' }}>
                    <TabsList>
                        <TabTrigger active={activeTab === 'skills'} onClick={() => setActiveTab('skills')}>
                            <Target size={16} /> Skills & Gaps
                        </TabTrigger>
                        <TabTrigger active={activeTab === 'recommendations'} onClick={() => setActiveTab('recommendations')}>
                            <Sparkles size={16} /> Recommendations
                        </TabTrigger>
                    </TabsList>

                    {activeTab === 'skills' && (
                        <Grid>
                            <Card>
                                <CardHeader>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f87171' }}>
                                        <AlertTriangle size={20} />
                                        <CardTitle>Missing Keywords</CardTitle>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '12px' }}>
                                        Use these exact keywords in your CV to pass ATS filters:
                                    </p>
                                    <div>
                                        {dashboardData.skills.missing.length > 0 ? (
                                            dashboardData.skills.missing.map((skill: any, idx: number) => (
                                                <SkillPill key={idx} name={skill.name || skill} tone="missing" />
                                            ))
                                        ) : (
                                            <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>No critical gaps detected. Good job!</div>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>

                            <Card style={{ gridColumn: 'span 2' }}>
                                <CardHeader>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#3b82f6' }}>
                                        <CheckCircle2 size={20} />
                                        <CardTitle>Skill Distribution Analysis</CardTitle>
                                    </div>
                                </CardHeader>
                                <CardContent style={{ height: '200px' }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <BarChart data={[
                                            { name: 'Found', value: dashboardData.score.skills, fill: '#10b981' },
                                            { name: 'Missing', value: 100 - dashboardData.score.skills, fill: '#ef4444' }
                                        ]} layout="vertical">
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                                            <XAxis type="number" hide />
                                            <YAxis dataKey="name" type="category" width={80} tick={{ fill: '#94a3b8' }} />
                                            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ background: '#1e293b', border: 'none' }} />
                                            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={32} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </CardContent>
                            </Card>
                        </Grid>
                    )}

                    {activeTab === 'recommendations' && (
                        <Card>
                            <CardHeader>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f59e0b' }}>
                                    <Sparkles size={20} />
                                    <CardTitle>AI Recommendations</CardTitle>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                    {data?.recommendations?.map((rec: string, idx: number) => (
                                        <li key={idx} style={{
                                            padding: '12px',
                                            marginBottom: '8px',
                                            background: 'rgba(255,255,255,0.03)',
                                            borderRadius: '8px',
                                            display: 'flex',
                                            gap: '12px',
                                            fontSize: '0.9rem'
                                        }}>
                                            <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>•</span>
                                            {rec}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    )}
                </div>

            </div>
        </DashboardContainer>
    );
}
