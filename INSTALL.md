# CINEOS Theater Installation Guide
US Prov. Pat. 64/049,190

## Requirements
- Device with Docker installed
- Network access to theater IP cameras via RTSP
- Internet connection for Railway API

## Installation in 4 steps

Step 1 - Install Docker
curl -fsSL https://get.docker.com | sh

Step 2 - Download CINEOS
git clone https://github.com/dbayugandhar-cmyk/cinerisk-api.git
cd cinerisk-api

Step 3 - Configure
cp .env.theater.example .env
Edit .env with your theater name, RTSP URLs, film titles

Step 4 - Deploy
docker-compose up -d

Verify with:
docker-compose logs -f

You should see:
[CINEOS] Stream open - monitoring YOUR THEATER Screen 1 for FILM TITLE

## Support
yugandhar@cineos.in
CINEOS Platform - US Prov. Pat. 64/049,190
