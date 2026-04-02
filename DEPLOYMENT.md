# 🚀 Ataraxia Bot - Production Deployment Guide

Deployment-Anleitung für **ataraxia-bot.com** auf einem Linux-Server

## 📋 Voraussetzungen

### Domain Setup
- **Domain:** ataraxia-bot.com
- **DNS A-Records:**
  - `ataraxia-bot.com` → Server IP
  - `www.ataraxia-bot.com` → Server IP
  - `api.ataraxia-bot.com` → Server IP (optional, für separate API-Domain)

---

## 🖥️ Server-Software installieren

### 1. System aktualisieren
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Python 3.11+ installieren
```bash
sudo apt install python3.11 python3.11-venv python3-pip -y
python3.11 --version
```

### 3. Node.js 18+ installieren
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y
node --version
npm --version
```

### 4. PostgreSQL (falls auf gleichem Server)
```bash
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 5. Nginx installieren
```bash
sudo apt install nginx -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 6. Certbot für SSL installieren
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 7. Git installieren (optional, für Deployment)
```bash
sudo apt install git -y
```

---

## 📦 Dateien auf Server hochladen

### Verzeichnisstruktur auf Server:
```
/opt/ataraxia/
├── bot/                   # Discord Bot (ehemals "Ataraxia" Ordner)
│   ├── main.py
│   ├── cogs/
│   ├── core/
│   ├── events/
│   ├── utils/
│   ├── requirements.txt
│   └── .env
│
├── api/                   # FastAPI Backend (separate Komponente)
│   ├── main.py
│   ├── requirements.txt
│   └── .env
│
└── dashboard/             # Next.js Frontend (separate Komponente)
    ├── app/
    ├── public/
    ├── package.json
    ├── next.config.ts
    └── .env.local
```

**💡 Tipp:** Auf deinem lokalen System solltest du die gleiche Struktur haben:
```
Serenity/
├── Ataraxia/          # Bot-Code (wird zu "bot" auf Server)
├── api/               # API-Code
└── dashboard/         # Dashboard-Code
```

### Dateien hochladen (via SCP/SFTP):
```bash
# Von deinem Windows PC aus (aus dem Serenity/ Verzeichnis):
scp -r Ataraxia/ user@server-ip:/opt/ataraxia/bot/
scp -r api/ user@server-ip:/opt/ataraxia/api/
scp -r dashboard/ user@server-ip:/opt/ataraxia/dashboard/
```

**Oder via Git (3 separate Repos empfohlen):**
```bash
cd /opt/ataraxia

# Bot
git clone https://github.com/dein-username/ataraxia-bot.git bot

# API
git clone https://github.com/dein-username/ataraxia-api.git api

# Dashboardbot
git clone https://github.com/dein-username/ataraxia-dashboard.git dashboard
```

**Oder Monorepo (alle zusammen):**
```bash
cd /opt/ataraxia
git clone https://github.com/dein-username/ataraxia.git .
# Dann hast du automatisch die Struktur mit bot/, api/, dashboard/
```

---

## ⚙️ Environment-Variablen konfigurieren

### 1. Bot `.env` (/opt/ataraxia/Ataraxia/.env)
```env
DISCORD_TOKEN=dein_discord_bot_token
DATABASE_URL=postgresql://user:password@localhost/ataraxia
OPENAI_API_KEY=dein_openai_key
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
DISCORD_CLIENT_ID=dein_client_id
DISCORD_CLIENT_SECRET=dein_client_secret

# NextAuth
NEXTAUTH_SECRET=generiere_einen_starken_secret
NEXTAUTH_URL=https://ataraxia-bot.com

# Discord Bot Token (für Discord API calls)
DISCORD_BOT_TOKEN=dein_discord_bot_token
```

**NEXTAUTH_SECRET generieren:**
```bash
openssl rand -base64 32
```

---

## 🔧 Services einrichten

### 1. Python Virtual Environment für Bot & API
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

**requirements.txt für API erstellen (falls noch nicht vorhanden):**
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

## 🔄 Systemd Services erstellen

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

### Services aktivieren und starten:
```bash
# Berechtigungen setzen
sudo chown -R www-data:www-data /opt/ataraxia

# Services aktivieren
sudo systemctl daemon-reload
sudo systemctl enable ataraxia-bot
sudo systemctl enable ataraxia-api
sudo systemctl enable ataraxia-dashboard

# Services starten
sudo systemctl start ataraxia-bot
sudo systemctl start ataraxia-api
sudo systemctl start ataraxia-dashboard

# Status überprüfen
sudo systemctl status ataraxia-bot
sudo systemctl status ataraxia-api
sudo systemctl status ataraxia-dashboard
```

---

## 🌐 Nginx Reverse Proxy konfigurieren

### Nginx Config erstellen:
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

    # SSL Zertifikate (werden von Certbot hinzugefügt)
    # ssl_certificate /etc/letsencrypt/live/ataraxia-bot.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/ataraxia-bot.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API Proxy (alle /api requests)
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

    # Dashboard Frontend (alle anderen requests)
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

### Nginx Config aktivieren:
```bash
# Symlink erstellen
sudo ln -s /etc/nginx/sites-available/ataraxia-bot.com /etc/nginx/sites-enabled/

# Nginx Config testen
sudo nginx -t

# Nginx neu laden
sudo systemctl reload nginx
```

---

## 🔒 SSL Zertifikat mit Let's Encrypt

```bash
# SSL Zertifikat für ataraxia-bot.com holen
sudo certbot --nginx -d ataraxia-bot.com -d www.ataraxia-bot.com

# Folge den Prompts:
# 1. Email eingeben
# 2. Terms akzeptieren
# 3. "Redirect HTTP to HTTPS" auswählen (Option 2)

# Certbot richtet automatisch SSL ein und aktualisiert die Nginx Config
```

**Auto-Renewal testen:**
```bash
sudo certbot renew --dry-run
```

---

## 🧪 Deployment testen

### 1. Services überprüfen:
```bash
# Logs anschauen
sudo journalctl -u ataraxia-bot -f
sudo journalctl -u ataraxia-api -f
sudo journalctl -u ataraxia-dashboard -f
```

### 2. API testen:
```bash
curl https://ataraxia-bot.com/api/health
# Expected: {"status": "healthy"}
```

### 3. Dashboard öffnen:
```
https://ataraxia-bot.com
```

### 4. Discord Bot Status:
```bash
# Bot sollte online sein
sudo systemctl status ataraxia-bot
```

---

## 🔄 Updates deployen

### Manuelles Update:
```bash
# Services stoppen
sudo systemctl stop ataraxia-bot
sudo systemctl stop ataraxia-api
sudo systemctl stop ataraxia-dashboard

# Neue Dateien hochladen (via SCP oder Git pull)
cd /opt/ataraxia
git pull

# Dashboard neu bauen
cd /opt/ataraxia/dashboard
npm install
npm run build

# Services neustarten
sudo systemctl start ataraxia-bot
sudo systemctl start ataraxia-api
sudo systemctl start ataraxia-dashboard
```

### Automatisches Deployment (Optional mit GitHub Actions):
Erstelle `.github/workflows/deploy.yml` im Repository.

---

## 📊 Monitoring & Logs

### Logs ansehen:
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

## 🛡️ Firewall einrichten (UFW)

```bash
# UFW installieren
sudo apt install ufw -y

# Default Policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Ports öffnen
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Firewall aktivieren
sudo ufw enable

# Status überprüfen
sudo ufw status
```

---

## 📝 Checkliste für Production

- [ ] DNS A-Records zeigen auf Server-IP
- [ ] PostgreSQL Datenbank läuft (lokal oder extern)
- [ ] Environment-Variablen gesetzt (.env Dateien)
- [ ] Python Virtual Environment erstellt & Dependencies installiert
- [ ] Dashboard gebaut (`npm run build`)
- [ ] Systemd Services erstellt und aktiviert
- [ ] Nginx Reverse Proxy konfiguriert
- [ ] SSL Zertifikat installiert (Let's Encrypt)
- [ ] Firewall konfiguriert (nur HTTP, HTTPS, SSH)
- [ ] Bot erscheint online in Discord
- [ ] API erreichbar unter `/api/health`
- [ ] Dashboard lädt unter `https://ataraxia-bot.com`
- [ ] Discord OAuth Login funktioniert
- [ ] Logs werden korrekt geschrieben

---

## 🚨 Troubleshooting

### Bot startet nicht:
```bash
sudo journalctl -u ataraxia-bot -n 50
# Check: Discord Token, Database Connection, Berechtigungen
```

### API 502 Bad Gateway:
```bash
sudo systemctl status ataraxia-api
# Check: Port 8000 läuft, Nginx Proxy Config
```

### Dashboard lädt nicht:
```bash
sudo systemctl status ataraxia-dashboard
cd /opt/ataraxia/dashboard
npm run build
# Check: .env.local, Build-Fehler
```

### SSL Probleme:
```bash
sudo certbot certificates
sudo nginx -t
# Check: Domain DNS, Nginx Config, Certbot Logs
```

---

## 📚 Nützliche Befehle

```bash
# Services neustarten
sudo systemctl restart ataraxia-bot
sudo systemctl restart ataraxia-api
sudo systemctl restart ataraxia-dashboard
sudo systemctl restart nginx

# Logs live ansehen
sudo journalctl -u ataraxia-bot -f

# Dashboard neu bauen
cd /opt/ataraxia/dashboard && npm run build

# Disk Space prüfen
df -h

# Memory Usage
free -h

# Process List
htop
```

---

## 🎉 Fertig!

Deine Ataraxia Bot Installation sollte jetzt auf **https://ataraxia-bot.com** laufen!

**URLs:**
- Dashboard: https://ataraxia-bot.com
- API Docs: https://ataraxia-bot.com/api/docs (FastAPI Swagger UI)
- Health Check: https://ataraxia-bot.com/api/health
