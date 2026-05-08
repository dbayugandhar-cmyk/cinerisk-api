"""
CINEOS Stream Fingerprinting Engine
Detects piracy by comparing audio/visual fingerprints
of official streams vs suspected piracy streams.

Legal: Only accesses publicly accessible streams.
No unauthorized access performed.
"""
import asyncio, httpx, subprocess, tempfile, os
import hashlib, json, datetime
from pathlib import Path

# ── AUDIO FINGERPRINTING ──────────────────────────────────
async def capture_stream_audio(stream_url: str, duration: int = 15) -> str:
    """Capture audio from a stream URL using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        tmp_path = f.name
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', stream_url,
            '-t', str(duration),
            '-vn',                    # no video
            '-ar', '22050',           # sample rate
            '-ac', '1',               # mono
            '-f', 'mp3',
            tmp_path,
            '-loglevel', 'quiet'
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=30)
        
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
            return tmp_path
    except Exception as e:
        print(f"Audio capture error: {e}")
    return None

def get_audio_fingerprint(audio_file: str) -> str:
    """Generate acoustic fingerprint using chromaprint."""
    try:
        import acoustid
        duration, fp = acoustid.fingerprint_file(audio_file)
        return fp.decode() if isinstance(fp, bytes) else fp
    except Exception as e:
        print(f"Fingerprint error: {e}")
        return None

def compare_fingerprints(fp1: str, fp2: str) -> float:
    """
    Compare two audio fingerprints.
    Returns similarity score 0.0 to 1.0
    """
    if not fp1 or not fp2:
        return 0.0
    try:
        import acoustid
        # Compare using chromaprint comparison
        # Simple approach: compare bit patterns
        min_len = min(len(fp1), len(fp2))
        if min_len == 0:
            return 0.0
        
        matches = sum(1 for a, b in zip(fp1[:min_len], fp2[:min_len]) if a == b)
        similarity = matches / min_len
        return round(similarity, 3)
    except:
        # Fallback: hash comparison
        h1 = hashlib.md5(fp1.encode()).hexdigest()
        h2 = hashlib.md5(fp2.encode()).hexdigest()
        return 1.0 if h1 == h2 else 0.0

# ── VISUAL FINGERPRINTING ─────────────────────────────────
async def capture_stream_frame(stream_url: str) -> str:
    """Capture a single frame from stream."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        tmp_path = f.name
    
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', stream_url,
            '-vframes', '1',
            '-ss', '5',           # skip 5 seconds
            '-f', 'image2',
            tmp_path,
            '-loglevel', 'quiet'
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=20)
        
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1000:
            return tmp_path
    except Exception as e:
        print(f"Frame capture error: {e}")
    return None

def get_frame_hash(image_file: str) -> str:
    """Generate perceptual hash of a frame."""
    try:
        import imagehash
        from PIL import Image
        img = Image.open(image_file)
        return str(imagehash.phash(img))
    except Exception as e:
        print(f"Hash error: {e}")
        return None

def compare_frame_hashes(h1: str, h2: str, threshold: int = 10) -> float:
    """
    Compare perceptual hashes.
    Returns similarity 0.0 to 1.0
    threshold: max hamming distance for match
    """
    if not h1 or not h2:
        return 0.0
    try:
        import imagehash
        hash1 = imagehash.hex_to_hash(h1)
        hash2 = imagehash.hex_to_hash(h2)
        distance = hash1 - hash2
        # Convert distance to similarity
        max_distance = 64  # max possible hamming distance
        similarity = 1.0 - (distance / max_distance)
        return round(max(0.0, similarity), 3)
    except:
        return 0.0

# ── HLS STREAM MONITOR ────────────────────────────────────
async def check_hls_stream(client: httpx.AsyncClient, url: str) -> dict:
    """Check if an HLS stream URL is live and get metadata."""
    try:
        r = await client.get(url, timeout=8,
            headers={"User-Agent": "VLC/3.0 LibVLC/3.0"})
        
        if r.status_code == 200:
            content = r.text[:2000]
            is_hls = '#EXTM3U' in content or '#EXT-X-' in content
            
            # Count segments (indicates activity)
            segments = content.count('.ts')
            
            # Get stream info
            bandwidth = 0
            resolution = ''
            for line in content.split('\n'):
                if 'BANDWIDTH=' in line:
                    try:
                        bandwidth = int(line.split('BANDWIDTH=')[1].split(',')[0])
                    except: pass
                if 'RESOLUTION=' in line:
                    try:
                        resolution = line.split('RESOLUTION=')[1].split(',')[0]
                    except: pass
            
            return {
                'live': True,
                'is_hls': is_hls,
                'segments': segments,
                'bandwidth_kbps': bandwidth // 1000,
                'resolution': resolution,
                'size': len(content)
            }
    except:
        pass
    return {'live': False}

# ── TELEGRAM STREAM FINDER ────────────────────────────────
async def find_stream_links(client: httpx.AsyncClient, channel: str) -> list:
    """Find stream links (.m3u8, stream URLs) in a Telegram channel."""
    stream_links = []
    try:
        r = await client.get(
            f"https://t.me/s/{channel}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            import re
            text = r.text
            
            # Find m3u8 links
            m3u8 = re.findall(r'https?://[^\s"<>]+\.m3u8[^\s"<>]*', text)
            stream_links.extend([{'url': u, 'type': 'hls'} for u in m3u8[:5]])
            
            # Find streaming platform links
            platforms = ['streameast', 'vipbox', 'cricfree', 'sportsurge',
                        'reddit', 'twitch', 'youtube']
            for platform in platforms:
                links = re.findall(
                    rf'https?://[^\s"<>]*{platform}[^\s"<>]*', text)
                stream_links.extend([
                    {'url': u, 'type': platform} for u in links[:2]])
    except:
        pass
    return stream_links[:10]

# ── MAIN FINGERPRINT SCAN ─────────────────────────────────
async def fingerprint_scan(
    event: str,
    official_stream_url: str = None,
    channels: list = None
) -> dict:
    """
    Full fingerprint scan for an event.
    Finds piracy streams and optionally compares to official stream.
    """
    print(f"[CINEOS-FP] Starting fingerprint scan: {event}")
    start = datetime.datetime.now()
    
    results = {
        'event': event,
        'scanned_at': start.isoformat(),
        'streams_found': [],
        'fingerprint_matches': [],
        'hls_streams': [],
        'summary': {}
    }
    
    # Default channels to scan
    if not channels:
        channels = [
            'IPL_L', 'RealCricPoint', 'CricketBetting', 'IPLBetting',
            'CricketStreamsLive', 'IPLstreams', 'CricketFreeStream',
            'SportsFreeStreams', 'LiveCricket', 'T20Live',
        ]
    
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True
    ) as client:
        
        print(f"[CINEOS-FP] Scanning {len(channels)} channels for stream links...")
        
        # Find stream links in channels
        link_tasks = [find_stream_links(client, ch) for ch in channels]
        all_links_results = await asyncio.gather(*link_tasks, return_exceptions=True)
        
        all_stream_links = []
        for ch, links in zip(channels, all_links_results):
            if isinstance(links, list) and links:
                for link in links:
                    link['channel'] = ch
                    all_stream_links.append(link)
                print(f"  @{ch}: {len(links)} stream links found")
        
        print(f"\n[CINEOS-FP] Found {len(all_stream_links)} stream links total")
        
        # Check HLS streams
        hls_links = [l for l in all_stream_links if l.get('type') == 'hls']
        if hls_links:
            print(f"[CINEOS-FP] Checking {len(hls_links)} HLS streams...")
            hls_tasks = [check_hls_stream(client, l['url']) for l in hls_links]
            hls_results = await asyncio.gather(*hls_tasks, return_exceptions=True)
            
            for link, result in zip(hls_links, hls_results):
                if isinstance(result, dict) and result.get('live'):
                    results['hls_streams'].append({
                        'url': link['url'],
                        'channel': link['channel'],
                        'resolution': result.get('resolution','unknown'),
                        'bandwidth_kbps': result.get('bandwidth_kbps', 0),
                        'confirmed_live': True
                    })
                    print(f"  LIVE HLS: {link['url'][:60]}")
        
        # If official stream provided — do fingerprint comparison
        if official_stream_url and all_stream_links:
            print(f"\n[CINEOS-FP] Capturing official stream fingerprint...")
            
            official_audio = await capture_stream_audio(official_stream_url, 15)
            official_fp = None
            official_frame = None
            official_hash = None
            
            if official_audio:
                official_fp = get_audio_fingerprint(official_audio)
                os.unlink(official_audio)
                print(f"  Official audio fingerprint: {official_fp[:20] if official_fp else 'FAILED'}...")
            
            official_frame = await capture_stream_frame(official_stream_url)
            if official_frame:
                official_hash = get_frame_hash(official_frame)
                os.unlink(official_frame)
                print(f"  Official frame hash: {official_hash}")
            
            # Compare against piracy streams
            if official_fp or official_hash:
                print(f"\n[CINEOS-FP] Comparing against {len(all_stream_links)} piracy streams...")
                
                for link in all_stream_links[:5]:  # limit to 5 comparisons
                    url = link['url']
                    print(f"  Comparing: {url[:50]}...")
                    
                    audio_sim = 0.0
                    frame_sim = 0.0
                    
                    if official_fp:
                        piracy_audio = await capture_stream_audio(url, 15)
                        if piracy_audio:
                            piracy_fp = get_audio_fingerprint(piracy_audio)
                            audio_sim = compare_fingerprints(official_fp, piracy_fp)
                            os.unlink(piracy_audio)
                    
                    if official_hash:
                        piracy_frame = await capture_stream_frame(url)
                        if piracy_frame:
                            piracy_hash = get_frame_hash(piracy_frame)
                            frame_sim = compare_frame_hashes(official_hash, piracy_hash)
                            os.unlink(piracy_frame)
                    
                    combined_sim = max(audio_sim, frame_sim)
                    
                    if combined_sim > 0.3:
                        match = {
                            'url': url,
                            'channel': link.get('channel','unknown'),
                            'audio_similarity': audio_sim,
                            'frame_similarity': frame_sim,
                            'combined_similarity': combined_sim,
                            'confirmed': combined_sim > 0.6,
                            'verdict': 'CONFIRMED PIRACY' if combined_sim > 0.6 else 'LIKELY PIRACY'
                        }
                        results['fingerprint_matches'].append(match)
                        print(f"    Match: {combined_sim:.1%} — {match['verdict']}")
    
    # Summary
    elapsed = (datetime.datetime.now() - start).total_seconds()
    results['summary'] = {
        'total_channels_scanned': len(channels),
        'stream_links_found': len(all_stream_links),
        'hls_streams_live': len(results['hls_streams']),
        'fingerprint_matches': len(results['fingerprint_matches']),
        'confirmed_piracy': len([m for m in results['fingerprint_matches'] 
                                 if m.get('confirmed')]),
        'scan_time_seconds': round(elapsed, 1)
    }
    
    print(f"\n[CINEOS-FP] Scan complete in {elapsed:.1f}s")
    print(f"  Stream links: {len(all_stream_links)}")
    print(f"  HLS live: {len(results['hls_streams'])}")
    print(f"  FP matches: {len(results['fingerprint_matches'])}")
    
    return results

if __name__ == '__main__':
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument('--event', default='IPL 2026')
    ap.add_argument('--official', default=None, 
                    help='Official stream URL for fingerprint comparison')
    ap.add_argument('--channels', nargs='+', default=None)
    args = ap.parse_args()
    
    result = asyncio.run(fingerprint_scan(
        args.event,
        official_stream_url=args.official,
        channels=args.channels
    ))
    
    print(f"\n{'='*65}")
    print(f"  CINEOS STREAM FINGERPRINT REPORT")
    print(f"  Event: {result['event']}")
    print(f"{'='*65}")
    s = result['summary']
    print(f"  Channels scanned : {s['total_channels_scanned']}")
    print(f"  Stream links     : {s['stream_links_found']}")
    print(f"  HLS live streams : {s['hls_streams_live']}")
    print(f"  FP matches       : {s['fingerprint_matches']}")
    print(f"  Confirmed piracy : {s['confirmed_piracy']}")
    print(f"  Scan time        : {s['scan_time_seconds']}s")
    
    if result['hls_streams']:
        print(f"\n  LIVE HLS STREAMS DETECTED:")
        for h in result['hls_streams']:
            print(f"  @{h['channel']:20} {h['resolution']:10} {h['url'][:50]}")
    
    if result['fingerprint_matches']:
        print(f"\n  FINGERPRINT MATCHES:")
        for m in result['fingerprint_matches']:
            print(f"  [{m['verdict']}] {m['combined_similarity']:.1%} match")
            print(f"  @{m['channel']} — {m['url'][:50]}")
    print(f"{'='*65}")
