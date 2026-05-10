# CINEOS Security Policy
**Version 1.0 | Effective May 3, 2026**
**US Provisional Patent 64/049,190**

---

## 1. Data Retention Policy

### Incident Records
- Theater incident records are retained for **24 months** from detection date
- Records include: zone, confidence score, timestamp, theater name, screen number, seat location
- Records do NOT include: video footage, facial recognition data, biometric data, personal identifiers
- After 24 months, records are anonymized and retained for aggregate statistical analysis only

### Scan Results
- Layer 4 internet scan results are retained for **12 months**
- Includes: film title, platform detected, gap minutes, scan timestamp

### Staff Reports
- Manual staff reports are retained for **24 months**
- Device IDs are stored as anonymous tokens, not linked to individual staff identities

### Deletion
- Data deletion requests processed within **30 business days**
- Theater operators may request full deletion of their theater's data at any time

---

## 2. Access Control Policy

### API Access
- All write operations require API key authentication (X-API-Key header)
- API keys are unique per theater deployment
- Keys are rotated every **90 days** or immediately upon suspected compromise
- Read endpoints (dashboards) require separate read-only API key

### Dashboard Access
- Studio compliance dashboards are accessible via unique per-studio URLs
- No login system currently — URL obscurity model (to be upgraded to auth in v2)
- Theater command centre access restricted to theater operators

### Database Access
- Railway PostgreSQL — access restricted to application service accounts only
- No direct DB access granted to third parties
- DB credentials rotated every **90 days**

### Staff App
- Theater selector limited to pre-configured theater list
- No user accounts or personal data collected from staff
- Device IDs are anonymous tokens generated at report time

---

## 3. Incident Response Plan

### Detection Events (Normal Operations)
1. YOLO detector identifies phone recording behavior
2. Incident auto-posted to Railway API with confidence score and zone
3. Staff app notified within 8 seconds
4. Layer 4 internet scan triggered within 10 minutes
5. Escalation emails sent at L2 (10 detections), L3 (30), L4 (60)

### Security Incidents (Breach or Compromise)

**Level 1 — Suspected API key compromise**
- Rotate API key immediately via Railway variables
- Review incident logs for unauthorized posts
- Notify affected theaters within **24 hours**

**Level 2 — Database breach**
- Isolate Railway service immediately
- Assess scope of exposed data
- Notify affected studios and theaters within **72 hours**
- File incident report with relevant authorities if PII involved
- Note: CINEOS does not store PII — exposure limited to zone/confidence/timestamp data

**Level 3 — Full system compromise**
- Take all Railway services offline
- Preserve logs for forensic analysis
- Notify all stakeholders within **24 hours**
- Engage cybersecurity incident response within **48 hours**

### Contact
Security incidents: yugandhar@cineos.in
Response SLA: 24 hours acknowledgment, 72 hours resolution plan

---

## 4. Privacy Policy Summary

### What CINEOS Collects
- Zone of detection (LEFT, CENTER, RIGHT)
- Confidence score (numerical value 0-1)
- Timestamp of detection
- Theater name and screen number
- Seat location (if provided by staff)
- Film title being screened
- Anonymous device ID (staff app only)

### What CINEOS Does NOT Collect
- Video footage or images
- Facial recognition data
- Biometric data
- Personal identifiers of audience members
- Names, emails, or contact information of patrons

### Legal Basis
- Theater operators consent to data collection via service agreement
- Audience members are subject to theater's existing "no recording" policy
- Detection is of devices, not individuals
- Compliant with US state privacy laws (CCPA basis: legitimate business interest)
- GDPR assessment required before European deployment

### Data Storage
- All data stored on Railway (US-West2 region)
- Data encrypted at rest and in transit
- No data sold or shared with third parties

---

## 5. MPA Content Security Best Practices Alignment

CINEOS is designed to align with MPA Content Security Best Practices v5.3 in the following areas:

| MPA Control Area | CINEOS Implementation |
|---|---|
| Physical Security | RTSP camera integration with existing theater CCTV |
| Technical Security | API key auth, HTTPS, DB encryption at rest |
| Incident Response | Automated escalation ladder L1-L4 |
| Content Monitoring | Layer 4 multi-source internet scan |
| Audit Logging | All incidents timestamped and hashed in PostgreSQL |

**TPN Assessment Status:** Planned Q4 2026

---

*CINEOS Platform | Yugandhar Mallavarapu | US Prov. Pat. 64/049,190*
*This document is confidential and intended for studio and theater partner review only*
