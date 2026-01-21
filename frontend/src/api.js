const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export const api = {
    async sendMessage(messages, sessionId, clientState) {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                messages,
                session_id: sessionId,
                client_state: clientState
            }),
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Server ${response.status}: ${text}`);
        }

        // ✅ return JSON (not stream)
        return await response.json();
    },
};
