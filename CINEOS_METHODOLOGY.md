# CINEOS Intelligence Methodology
## Patent US Provisional 64/049,190

### Entity Identification
1. Channel discovery via keyword seeding across 14 fraud categories
2. Phone extraction: regex pattern matching on 10-digit Indian mobile numbers
3. UPI extraction: pattern matching on UPI handle formats
4. Domain extraction: monitoring for brand-similar registrations

### Attribution Process
1. Single channel with phone = 70% confidence
2. Same phone in 2 channels = 80% confidence  
3. Same phone in 3+ channels = 90-95% confidence
4. Phone + UPI + domain convergence = 99% confidence

### Evidence Certification
1. SHA-256 hash generated at moment of detection
2. Timestamp recorded in IST
3. Sample post preserved verbatim
4. IT Act 2000 §65B compliant certificate generated

### Cross-Reference Engine
1. Enforcement news fetched every 2 hours (10 query categories)
2. Entities extracted from news articles
3. Matched against database using exact and fuzzy matching
4. Confidence scored: 100% phone match, 95% channel match, 70% category+state

### Operator Network Mapping
1. Phone node created for each extracted number
2. Edge created between phone and channel
3. Cross-channel edges reveal operator networks
4. Network confidence = max(individual channel confidences)


## Explainable Confidence Scores

| Factor | Score |
|--------|-------|
| Base | 70% |
| Phone extracted x1 | +5% |
| Phone extracted x2 | +10% |
| Phone extracted x3+ | +15% |
| Same phone 2 channels | +5% |
| Same phone 3-4 channels | +10% |
| Same phone 5+ channels | +15% |
| UPI extracted | +5% |
| Sample post preserved | +3% |
| High-risk category | +2% |

Example: Score 92% means phone in 7 channels (+15%), 3 phones total (+15%), UPI found (+5%), minus base adjustments.

## IT Act 2000 §65B(2) Full Certificate

All five conditions documented per case:
(a) Activity description, (b) System functioning, (c) Ordinary course,
(d) Regular storage, (e) Certifying identity

## Vertical Configurations

configs/betting.json — Illegal Betting and Match Fixing
configs/pharma.json  — Counterfeit Pharmaceuticals
configs/fintech.json — Financial Fraud and UPI Mule Networks
