# 🚀 Ataraxia Bot - Production Deployment Guide

Deployment-Tutorial for **ataraxia-bot.com** on a Linux-Server

## 📋 Prerequisites

### Domain Setup
- **Domain:** ataraxia-bot.com
- **DNS A-Records:**
  - `ataraxia-bot.com` → Server IP
  - `www.ataraxia-bot.com` → Server IP
  - `api.ataraxia-bot.com` → Server IP (optional, for separate API-Domain)

---

## 🖥️ Install Server-Software

### 1. update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. installing Python 3.11+
```bash
sudo apt install python3.11 python3.11-venv python3-pip -y
python3.11 --version
```

### 3. installing Node.js 18+
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
node --version
npm --version
```

### 4. PostgreSQL (if on the same server)
```bash
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 5. installing Nginx
```bash
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 6. installing Certbot for SSL
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 7. installing Git (optional, for Deployment)
```bash
sudo apt install git -y
```

---

## 📦 Upload files to Server

### Folder structure on Server:
```
/opt/ataraxia/
├── bot/                   # Discord Bot (once "Ataraxia" Folder)
│   ├── main.py
│   ├── cogs/
│   ├── core/
│   ├── events/
│   ├── utils/
│   ├── requirements.txt
│   └── .env
│
├── api/                   # FastAPI Backend (separate component)
│   ├── main.py
│   ├── requirements.txt
│   └── .env
│
└── dashboard/             # Next.js Frontend (separate component)
    ├── app/
    ├── public/
    ├── package.json
    ├── next.config.ts
    └── .env.local
```

**💡 Hint:** You should have the same structure on your local system:
```
Serenity/
├── Ataraxia/          # Bot-Code (will be "bot" on Server)
├── api/               # API-Code
└── dashboard/         # Dashboard-Code
```

### Upload Files (via SCP/SFTP):
```bash
# On Windows (from Parent Folder):
scp -r Ataraxia/ user@server-ip:/opt/ataraxia/bot/
scp -r api/ user@server-ip:/opt/ataraxia/api/
scp -r dashboard/ user@server-ip:/opt/ataraxia/dashboard/
```

**Or via Git (3 separate Repos empfohlen):**
```bash
cd /opt/ataraxia

# Bot
git clone https://github.com/your-username/ataraxia-bot.git bot

# API
git clone https://github.com/your-username/ataraxia-api.git api

# Dashboardbot
git clone https://github.com/your-username/ataraxia-dashboard.git dashboard
```

**or Monorepo (all at once):**
```bash
cd /opt/ataraxia
git clone https://github.com/your-username/ataraxia.git .
# You'll have the same structure with bot/, api/, dashboard/
```

---

## ⚙️ configure Environment-Vars

### 1. Bot `.env` (/opt/ataraxia/Ataraxia/.env)
```env
DISCORD_TOKEN=your_discord_bot_token
DATABASE_URL=postgresql://user:password@localhost/ataraxia
OPENAI_API_KEY=your_openai_key
```

### 2. API `.env` (/opt/ataraxia/api/.env)
```env
DATABASE_URL=postgresql://user:password@localhost/ataraxia
```

### 3. Dashboard `.env.local` (/opt/ataraxia/dashboard/.env.local)
```env
# API Configuration
NEXT_PUBLIC_API_URL=https://ataraxia-bot.com/api
NEXT_PUBLIC_USE_MOCK_DATA=false

# Discord OAuth
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret

# NextAuth
NEXTAUTH_SECRET=generate_a_strong_secret
NEXTAUTH_URL=https://ataraxia-bot.com

# Discord Bot Token (for Discord API calls)
DISCORD_BOT_TOKEN=your_discord_bot_token
```

**Generate NEXTAUTH_SECRET:**
```bash
openssl rand -base64 32
```

---

## 🔧 Implement Services

### 1. Python Virtual Environment for Bot & API
```bash
cd /opt/ataraxia
python3.11 -m venv venv
source venv/bin/activate

# Bot Dependencies
cd /opt/ataraxia/bot
pip install -r requirements.txt

# API Dependencies
cd /opt/ataraxia/api
pip install -r requirements.txt
```

**create requirements.txt for API (if not yet):**
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
asyncpg==0.29.0
pydantic==2.5.0
python-dotenv==1.0.0
```

### 2. Dashboard Build
```bash
cd /opt/ataraxia/dashboard
npm install
npm run build
```

---

## 🔄 Create Systemd Services

### 1. Discord Bot Service
```bash
sudo nano /etc/systemd/system/ataraxia-bot.service
```

```ini
[Unit]
Description=Ataraxia Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ataraxia/bot
Environment="PATH=/opt/ataraxia/venv/bin"
ExecStart=/opt/ataraxia/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. FastAPI Service
```bash
sudo nano /etc/systemd/system/ataraxia-api.service
```

```ini
[Unit]
Description=Ataraxia FastAPI Backend
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ataraxia/api
Environment="PATH=/opt/ataraxia/venv/bin"
ExecStart=/opt/ataraxia/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Next.js Dashboard Service
```bash
sudo nano /etc/systemd/system/ataraxia-dashboard.service
```

```ini
[Unit]
Description=Ataraxia Next.js Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ataraxia/dashboard
Environment="NODE_ENV=production"
Environment="PORT=3000"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Activate and start Services:
```bash
# set Permission
sudo chown -R www-data:www-data /opt/ataraxia

# activate Services
sudo systemctl daemon-reload
sudo systemctl enable ataraxia-bot
sudo systemctl enable ataraxia-api
sudo systemctl enable ataraxia-dashboard

# start Services
sudo systemctl start ataraxia-bot
sudo systemctl start ataraxia-api
sudo systemctl start ataraxia-dashboard

# check Status
sudo systemctl status ataraxia-bot
sudo systemctl status ataraxia-api
sudo systemctl status ataraxia-dashboard
```

---

## 🌐 Nginx Reverse Proxy Configuration

### Create Nginx Config:
```bash
sudo nano /etc/nginx/sites-available/ataraxia-bot.com
```

```nginx
# API Backend (Port 8000)
upstream api_backend {
    server 127.0.0.1:8000;
}

# Next.js Frontend (Port 3000)
upstream dashboard_frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name ataraxia-bot.com www.ataraxia-bot.com;

    # Redirect to HTTPS (wird später von Certbot automatisch hinzugefügt)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ataraxia-bot.com www.ataraxia-bot.com;

    # SSL certificates (will be added by Certbot)
    # ssl_certificate /etc/letsencrypt/live/ataraxia-bot.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/ataraxia-bot.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API Proxy (all /api requests)
    location /api/ {
        proxy_pass http://api_backend/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Dashboard Frontend (all other requests)
    location / {
        proxy_pass http://dashboard_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Static files optimization
    location /_next/static {
        proxy_pass http://dashboard_frontend;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # File upload size limit
    client_max_body_size 10M;
}
```

### Activate Nginx Config:
```bash
# create Symlink
sudo ln -s /etc/nginx/sites-available/ataraxia-bot.com /etc/nginx/sites-enabled/

# test Nginx Config
sudo nginx -t

# reload Nginx
sudo systemctl reload nginx
```

---

## 🔒 SSL Certificate via Let's Encrypt

```bash
# get SSL Zertifikat for ataraxia-bot.com
sudo certbot --nginx -d ataraxia-bot.com -d www.ataraxia-bot.com

# Follow the Prompts:
# 1. input Email
# 2. accept Terms
# 3. select "Redirect HTTP to HTTPS" (Option 2)

# Certbot automatically implements SSL and updates the Nginx Config
```

**test Auto-Renewal:**
```bash
sudo certbot renew --dry-run
```

---

## 🧪 test Deployment

### 1. monitor Services:
```bash
# check logs
sudo journalctl -u ataraxia-bot -f
sudo journalctl -u ataraxia-api -f
sudo journalctl -u ataraxia-dashboard -f
```

### 2. test API:
```bash
curl https://ataraxia-bot.com/api/health
# Expected: {"status": "healthy"}
```

### 3. open Dashboard:
```
https://ataraxia-bot.com
```

### 4. Discord Bot Status:
```bash
# Bot should be online
sudo systemctl status ataraxia-bot
```

---

## 🔄 deploy Updates

### manual Update:
```bash
# stop Services
sudo systemctl stop ataraxia-bot
sudo systemctl stop ataraxia-api
sudo systemctl stop ataraxia-dashboard

# upload new file (via SCP or Git pull)
cd /opt/ataraxia
git pull

# rebuild dashboard
cd /opt/ataraxia/dashboard
npm install
npm run build

# start Services
sudo systemctl start ataraxia-bot
sudo systemctl start ataraxia-api
sudo systemctl start ataraxia-dashboard
```

### automatic Deployment (optional via GitHub Actions):
create `.github/workflows/deploy.yml` in the Repository.

---

## 📊 Monitoring & Logs

### check Logs:
```bash
# Bot Logs
sudo journalctl -u ataraxia-bot -n 100 --no-pager

# API Logs
sudo journalctl -u ataraxia-api -n 100 --no-pager

# Dashboard Logs
sudo journalctl -u ataraxia-dashboard -n 100 --no-pager

# Nginx Logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Service Status:
```bash
sudo systemctl status ataraxia-bot
sudo systemctl status ataraxia-api
sudo systemctl status ataraxia-dashboard
sudo systemctl status nginx
```

---

## 🛡️ implement Firewall (UFW)

```bash
# install UFW
sudo apt install ufw -y

# Default Policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# open ports
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# activate firewall
sudo ufw enable

# check Status
sudo ufw status
```

---

## 📝 Checklist for production

- [ ] DNS A-Records point to Server-IP
- [ ] PostgreSQL database is running (local or external)
- [ ] set Environment-Vars  (.env files)
- [ ] Python Virtual Environment created & Dependencies installed
- [ ] Dashboard built (`npm run build`)
- [ ] Systemd Services created and activated
- [ ] Nginx Reverse Proxy configured
- [ ] SSL Zertifikat installed (Let's Encrypt)
- [ ] Firewall configured (only HTTP, HTTPS, SSH)
- [ ] Bot appears online in Discord
- [ ] API reachable under `/api/health`
- [ ] Dashboard loading under `https://ataraxia-bot.com`
- [ ] Discord OAuth Login is working
- [ ] Logs are written correctly

---

## 🚨 Troubleshooting

### Bot not starting:
```bash
sudo journalctl -u ataraxia-bot -n 50
# Check: Discord Token, Database Connection, Berechtigungen
```

### API 502 Bad Gateway:
```bash
sudo systemctl status ataraxia-api
# Check: Port 8000 läuft, Nginx Proxy Config
```

### Dashboard not loading:
```bash
sudo systemctl status ataraxia-dashboard
cd /opt/ataraxia/dashboard
npm run build
# Check: .env.local, Build-Fehler
```

### SSL Problems:
```bash
sudo certbot certificates
sudo nginx -t
# Check: Domain DNS, Nginx Config, Certbot Logs
```

---

## 📚 Useful Commands

```bash
# restart services
sudo systemctl restart ataraxia-bot
sudo systemctl restart ataraxia-api
sudo systemctl restart ataraxia-dashboard
sudo systemctl restart nginx

# watch logs live
sudo journalctl -u ataraxia-bot -f

# rebuild dashboard
cd /opt/ataraxia/dashboard && npm run build

# check disk space
df -h

# Memory Usage
free -h

# Process List
htop
```

---

## 🎉 Done!

Your Ataraxia Bot installation should run on **https://ataraxia-bot.com**

**URLs:**
- Dashboard: https://ataraxia-bot.com
- API Docs: https://ataraxia-bot.com/api/docs (FastAPI Swagger UI)
- Health Check: https://ataraxia-bot.com/api/health
