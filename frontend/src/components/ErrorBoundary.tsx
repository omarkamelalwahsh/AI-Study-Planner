import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="error-boundary" style={{ padding: '20px', textAlign: 'center', background: '#1a1a1a', color: '#fff', borderRadius: '8px', margin: '20px' }}>
                    <h2>⚠️ عذراً، حدث خطأ غير متوقع</h2>
                    <p>يبدو أن هناك مشكلة في عرض هذه المحادثة. حاول إعادة تحميل الصفحة.</p>
                    <button
                        onClick={() => window.location.reload()}
                        style={{
                            padding: '10px 20px',
                            background: '#8b5cf6',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '5px',
                            cursor: 'pointer',
                            marginTop: '10px'
                        }}
                    >
                        إعادة تحميل 🔄
                    </button>
                    {import.meta.env.DEV && (
                        <pre style={{ textAlign: 'left', background: '#333', padding: '10px', marginTop: '20px', overflow: 'auto', fontSize: '0.8rem' }}>
                            {this.state.error?.toString()}
                        </pre>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
