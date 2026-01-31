import ChatInterface from './components/ChatInterface'
import ErrorBoundary from './components/ErrorBoundary'

function App() {
    return (
        <div className="app">
            <header className="app-header">
                <div className="container">
                    <h1>🎓 Career Copilot</h1>
                    <p>مساعدك الذكي للتوجيه المهني واختيار الكورسات</p>
                </div>
            </header>

            <main className="app-main">
                <div className="container">
                    <ErrorBoundary>
                        <ChatInterface />
                    </ErrorBoundary>
                </div>
            </main>

            <footer className="app-footer">
                <div className="container">
                    <p>© {new Date().getFullYear()} Career Copilot</p>
                </div>
            </footer>
        </div>
    )
}

export default App
