# Deployment Guide

This guide covers how to deploy Career Copilot RAG to a production environment.

## 🐳 Docker Deployment (Recommended)

### 1. Build the Image

```bash
docker build -t career-copilot .
```

### 2. Run the Container

```bash
docker run -d \
  -p 8000:8000 \
  -e GROQ_API_KEY="your_key_here" \
  career-copilot
```

---

## 🐧 Linux / VPS Deployment

### 1. System Requirements

- Ubuntu 22.04 LTS (Recommended)
- Python 3.11+
- Node.js 18+
- Nginx (Reverse Proxy)

### 2. Setup Backend (Systemd)

Create a service file `/etc/systemd/system/career-copilot.service`:

```ini
[Unit]
Description=Career Copilot Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/career-copilot
ExecStart=/home/ubuntu/career-copilot/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Setup Frontend (Static)

Build the frontend locally or on server:

```bash
cd frontend
npm install
npm run build
```

Serve the `dist/` folder using Nginx.

### 4. Nginx Configuration

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        root /home/ubuntu/career-copilot/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
