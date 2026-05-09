"""
CINEOS Event Risk Scorer
Predicts piracy risk BEFORE a film releases.
Based on historical piracy patterns.
"""
import asyncio, httpx, json, os
from datetime import datetime

SERP_KEY = os.environ.get('SERP_API_KEY','')

# Risk factors based on historical data
RISK_FACTORS = {
    # Language risk (Tamil/Telugu highest piracy rates)
    'language': {
        'Telugu': 35, 'Tamil': 35, 'Malayalam': 30,
        'Hindi': 25, 'Kannada': 20, 'English': 10
    },
    # Platform risk
    'platform': {
        'Amazon Prime Video': 30, 'Netflix': 20,
        'ZEE5': 35, 'JioHotstar': 25, 'SonyLIV': 20,
        'AHA': 30, 'Theatrical': 40
    },
    # Genre risk
    'genre': {
        'Action': 35, 'Thriller': 30, 'Drama': 20,
        'Comedy': 15, 'Horror': 25, 'Romance': 15
    },
}

async def calculate_risk_score(
    title: str,
    language: str = 'Telugu',
    platform: str = 'Amazon Prime Video',
    genre: str = 'Action',
    release_date: str = None,
    star_power: str = 'high'  # high/medium/low
) -> dict:
    """
    Calculate piracy risk score for an upcoming release.
    Returns 0-100 risk score with breakdown.
    """
    print(f"[RISK] Scoring: {title}")
    
    score = 0
    factors = {}
    
    # Base scores from risk factors
    lang_score = RISK_FACTORS['language'].get(language, 20)
    plat_score = RISK_FACTORS['platform'].get(platform, 25)
    genre_score = RISK_FACTORS['genre'].get(genre, 20)
    
    factors['language'] = {'score': lang_score, 'reason': f'{language} content has high piracy rate'}
    factors['platform'] = {'score': plat_score, 'reason': f'{platform} frequently targeted'}
    factors['genre'] = {'score': genre_score, 'reason': f'{genre} films attract pirates'}
    
    # Star power factor
    star_scores = {'high': 25, 'medium': 15, 'low': 5}
    star_score = star_scores.get(star_power, 15)
    factors['star_power'] = {'score': star_score, 'reason': 'High-profile cast increases piracy demand'}
    
    # Release timing factor
    if release_date:
        try:
            rd = datetime.strptime(release_date, '%Y-%m-%d')
            now = datetime.now()
            days_until = (rd - now).days
            if days_until < 0:
                timing_score = 20  # already released
            elif days_until < 7:
                timing_score = 30  # releasing soon — high risk
            elif days_until < 30:
                timing_score = 20  # releasing this month
            else:
                timing_score = 10  # far out
            factors['timing'] = {'score': timing_score, 'reason': f'{abs(days_until)} days {"past" if days_until<0 else "until"} release'}
        except:
            timing_score = 15
            factors['timing'] = {'score': timing_score, 'reason': 'Release date factor'}
    else:
        timing_score = 15
        factors['timing'] = {'score': timing_score, 'reason': 'No release date provided'}
    
    # Historical precedent — check if similar titles were pirated
    historical_score = 0
    if SERP_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://serpapi.com/search", params={
                    "q": f'"{title}" tamilblasters OR movierulz OR filmyzilla download',
                    "api_key": SERP_KEY, "num": 5, "engine": "google"
                })
                hits = len(r.json().get("organic_results", []))
                historical_score = min(hits * 5, 25)
                factors['existing_piracy'] = {
                    'score': historical_score,
                    'reason': f'{hits} piracy URLs already found online'
                }
        except:
            pass
    
    # Total weighted score
    total = lang_score + plat_score + genre_score + star_score + timing_score + historical_score
    # Normalize to 0-100
    max_possible = 35 + 40 + 35 + 25 + 30 + 25
    normalized = min(int((total / max_possible) * 100), 100)
    
    # Risk level
    if normalized >= 75:
        level = 'CRITICAL'
        color = 'red'
        action = 'Deploy CINEOS monitoring immediately. Pre-register DMCA. Alert CDN.'
    elif normalized >= 55:
        level = 'HIGH'
        color = 'orange'
        action = 'Schedule monitoring from release day. Prepare evidence templates.'
    elif normalized >= 35:
        level = 'MEDIUM'
        color = 'yellow'
        action = 'Monitor weekly. Set up alerts for first 30 days.'
    else:
        level = 'LOW'
        color = 'green'
        action = 'Standard monitoring sufficient.'
    
    return {
        'title': title,
        'risk_score': normalized,
        'risk_level': level,
        'factors': factors,
        'total_raw': total,
        'recommended_action': action,
        'inputs': {
            'language': language,
            'platform': platform,
            'genre': genre,
            'star_power': star_power,
            'release_date': release_date
        }
    }

async def score_upcoming_releases(releases: list) -> list:
    """Score multiple upcoming releases."""
    results = []
    for r in releases:
        score = await calculate_risk_score(**r)
        results.append(score)
        print(f"  {r['title']:30} {score['risk_level']:8} {score['risk_score']}/100")
    return sorted(results, key=lambda x: -x['risk_score'])

if __name__ == '__main__':
    # Score this week's and next week's releases
    upcoming = [
        {'title':'Dacoit', 'language':'Telugu',
         'platform':'Amazon Prime Video', 'genre':'Action',
         'release_date':'2026-05-08', 'star_power':'high'},
        {'title':'Biker', 'language':'Telugu',
         'platform':'Netflix', 'genre':'Action',
         'release_date':'2026-05-01', 'star_power':'high'},
        {'title':'Aadu 3', 'language':'Malayalam',
         'platform':'ZEE5', 'genre':'Comedy',
         'release_date':'2026-05-01', 'star_power':'high'},
        {'title':'Lukkhe', 'language':'Hindi',
         'platform':'Amazon Prime Video', 'genre':'Action',
         'release_date':'2026-05-08', 'star_power':'medium'},
        {'title':'Citadel Season 2', 'language':'English',
         'platform':'Amazon Prime Video', 'genre':'Thriller',
         'release_date':'2026-05-08', 'star_power':'high'},
    ]
    
    print("CINEOS RISK SCORING — UPCOMING RELEASES")
    print("="*60)
    results = asyncio.run(score_upcoming_releases(upcoming))
    
    print(f"\nDETAILED BREAKDOWN:")
    for r in results:
        print(f"\n  {r['title']} — {r['risk_level']} ({r['risk_score']}/100)")
        for factor, data in r['factors'].items():
            print(f"    {factor:20} +{data['score']:2} — {data['reason']}")
        print(f"    ACTION: {r['recommended_action']}")
