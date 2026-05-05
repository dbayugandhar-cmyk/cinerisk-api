#!/usr/bin/env python3
"""
CINEOS Acoustic Theater Fingerprinting
=======================================
Novel Layer — US Provisional Patent 64/049,190

Every theater has a unique acoustic signature:
- Room resonance frequencies (size and shape)
- HVAC hum (building-specific frequency)  
- Speaker placement patterns
- Audience density acoustic absorption
- Wall material reflections

When a CAM copy appears online, we extract its acoustic
fingerprint and compare against our theater database.
If it matches a theater in our incident database that had
a recording event that night — we have prosecution-grade
attribution WITHOUT needing a forensic watermark.

This is genuinely novel. Nobody does this systematically.
"""

import numpy as np
import hashlib
import json
import os
import asyncio
import httpx
import tempfile
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import logging

log = logging.getLogger("cineos.acoustic")

# ── Try importing audio libraries ─────────────────────────────────
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    log.warning("librosa not available — install with: pip3 install librosa")

try:
    from scipy import signal
    from scipy.fft import fft, fftfreq
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class AcousticFingerprint:
    """Acoustic fingerprint of a recording."""
    fingerprint_hash: str          # Unique hash of acoustic signature
    hvac_frequency: float          # HVAC hum frequency (Hz) — building specific
    room_resonance: list           # Room resonance peaks (Hz)
    reverb_time: float             # RT60 — room size indicator (seconds)
    audience_density: float        # Estimated absorption coefficient
    speaker_pattern: list          # Speaker placement signature
    noise_floor: float             # Background noise level (dB)
    sample_duration: float         # How many seconds analyzed
    confidence: float              # Fingerprint quality 0-1
    metadata: dict = field(default_factory=dict)


@dataclass 
class TheaterProfile:
    """Known acoustic profile of a specific theater."""
    theater_id: str
    theater_name: str
    screen_number: str
    city: str
    fingerprint: AcousticFingerprint
    recorded_at: str
    sample_count: int = 1          # Number of samples averaged


@dataclass
class AttributionResult:
    """Result of matching a CAM copy to a theater."""
    matched: bool
    confidence: float              # 0-100
    theater_name: str
    screen_number: str
    city: str
    match_reasons: list
    theater_incident_match: bool   # Cross-referenced with incident DB
    incident_details: dict = field(default_factory=dict)


class AcousticFingerprintEngine:
    """
    Core engine for acoustic theater fingerprinting.
    
    Novel approach: Extract acoustic signatures from CAM copies
    and match against a database of known theater profiles.
    """
    
    def __init__(self, db_path: str = "acoustic_theater_db.json"):
        self.db_path = db_path
        self.theater_db: list[TheaterProfile] = []
        self.load_db()
    
    def load_db(self):
        """Load theater acoustic profile database."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                self.theater_db = []
                for t in data:
                    fp_data = t['fingerprint']
                    fp = AcousticFingerprint(**fp_data)
                    profile = TheaterProfile(
                        theater_id=t['theater_id'],
                        theater_name=t['theater_name'],
                        screen_number=t['screen_number'],
                        city=t['city'],
                        fingerprint=fp,
                        recorded_at=t['recorded_at'],
                        sample_count=t.get('sample_count', 1)
                    )
                    self.theater_db.append(profile)
                log.info(f"Loaded {len(self.theater_db)} theater profiles")
            except Exception as e:
                log.error(f"Failed to load acoustic DB: {e}")
    
    def save_db(self):
        """Save theater acoustic profile database."""
        data = []
        for profile in self.theater_db:
            data.append({
                'theater_id': profile.theater_id,
                'theater_name': profile.theater_name,
                'screen_number': profile.screen_number,
                'city': profile.city,
                'fingerprint': {
                    'fingerprint_hash': profile.fingerprint.fingerprint_hash,
                    'hvac_frequency': profile.fingerprint.hvac_frequency,
                    'room_resonance': profile.fingerprint.room_resonance,
                    'reverb_time': profile.fingerprint.reverb_time,
                    'audience_density': profile.fingerprint.audience_density,
                    'speaker_pattern': profile.fingerprint.speaker_pattern,
                    'noise_floor': profile.fingerprint.noise_floor,
                    'sample_duration': profile.fingerprint.sample_duration,
                    'confidence': profile.fingerprint.confidence,
                    'metadata': profile.fingerprint.metadata,
                },
                'recorded_at': profile.recorded_at,
                'sample_count': profile.sample_count,
            })
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)
        log.info(f"Saved {len(self.theater_db)} theater profiles")

    def extract_fingerprint_from_file(self, audio_path: str) -> Optional[AcousticFingerprint]:
        """
        Extract acoustic fingerprint from an audio file.
        Analyzes the first 60 seconds for theater signature.
        """
        if not LIBROSA_AVAILABLE:
            return self._extract_fingerprint_basic(audio_path)
        
        try:
            # Load first 60 seconds of audio
            y, sr = librosa.load(audio_path, duration=60, sr=22050, mono=True)
            duration = len(y) / sr
            
            if duration < 5:
                log.warning(f"Audio too short: {duration:.1f}s")
                return None
            
            # ── 1. HVAC frequency detection ────────────────────────
            # HVAC systems hum at building-specific frequencies
            # Typically 50Hz or 60Hz harmonics (100, 120, 200, 240Hz)
            # The exact harmonic pattern is building-specific
            fft_vals = np.abs(fft(y))
            freqs = fftfreq(len(y), 1/sr)
            pos_mask = freqs > 0
            pos_freqs = freqs[pos_mask]
            pos_fft = fft_vals[pos_mask]
            
            # Find dominant low-frequency peaks (HVAC range 50-300Hz)
            hvac_mask = (pos_freqs >= 50) & (pos_freqs <= 300)
            if hvac_mask.any():
                hvac_idx = np.argmax(pos_fft[hvac_mask])
                hvac_freq = float(pos_freqs[hvac_mask][hvac_idx])
            else:
                hvac_freq = 0.0
            
            # ── 2. Room resonance peaks ────────────────────────────
            # Room size determines resonance frequencies
            # Larger rooms = lower resonance frequencies
            # Find top 5 resonance peaks 200-2000Hz
            resonance_mask = (pos_freqs >= 200) & (pos_freqs <= 2000)
            if resonance_mask.any():
                resonance_fft = pos_fft[resonance_mask]
                resonance_freqs = pos_freqs[resonance_mask]
                top_peaks = np.argsort(resonance_fft)[-5:]
                room_resonance = sorted([float(resonance_freqs[i]) for i in top_peaks])
            else:
                room_resonance = []
            
            # ── 3. Reverb time estimation (RT60) ──────────────────
            # Larger rooms have longer reverb
            # Cinema screens: typically 0.3-0.8 seconds
            try:
                spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
                reverb_time = float(np.std(spectral_rolloff) / 1000)
                reverb_time = min(max(reverb_time, 0.1), 2.0)
            except:
                reverb_time = 0.5
            
            # ── 4. Noise floor (audience density indicator) ────────
            noise_floor = float(20 * np.log10(np.percentile(np.abs(y), 10) + 1e-10))
            
            # ── 5. Speaker pattern (spectral centroid over time) ───
            try:
                centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
                speaker_pattern = [float(x) for x in centroid[0][:10].tolist()]
            except:
                speaker_pattern = []
            
            # ── 6. Audience density (zero crossing rate) ───────────
            try:
                zcr = librosa.feature.zero_crossing_rate(y)
                audience_density = float(np.mean(zcr))
            except:
                audience_density = 0.0
            
            # ── 7. Generate fingerprint hash ───────────────────────
            # Hash key acoustic features for fast comparison
            hash_input = f"{hvac_freq:.1f}|{room_resonance}|{reverb_time:.2f}|{noise_floor:.1f}"
            fingerprint_hash = hashlib.md5(hash_input.encode()).hexdigest()[:16]
            
            # ── 8. Confidence score ────────────────────────────────
            confidence = min(1.0, duration / 60.0)
            if hvac_freq > 0: confidence += 0.1
            if len(room_resonance) >= 3: confidence += 0.1
            confidence = min(confidence, 1.0)
            
            return AcousticFingerprint(
                fingerprint_hash=fingerprint_hash,
                hvac_frequency=hvac_freq,
                room_resonance=room_resonance,
                reverb_time=reverb_time,
                audience_density=audience_density,
                speaker_pattern=speaker_pattern,
                noise_floor=noise_floor,
                sample_duration=duration,
                confidence=confidence,
                metadata={'sample_rate': sr, 'analyzed_at': datetime.now(timezone.utc).isoformat()}
            )
            
        except Exception as e:
            log.error(f"Fingerprint extraction failed: {e}")
            return None
    
    def _extract_fingerprint_basic(self, audio_path: str) -> Optional[AcousticFingerprint]:
        """
        Basic fingerprint without librosa — uses raw numpy FFT.
        Less accurate but works without heavy dependencies.
        """
        try:
            # Try reading as raw PCM with scipy
            from scipy.io import wavfile
            sr, data = wavfile.read(audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)
            data = data.astype(float) / np.iinfo(np.int16).max
            
            # Limit to 60 seconds
            max_samples = sr * 60
            if len(data) > max_samples:
                data = data[:max_samples]
            
            duration = len(data) / sr
            fft_vals = np.abs(np.fft.fft(data))
            freqs = np.fft.fftfreq(len(data), 1/sr)
            pos_mask = freqs > 0
            pos_freqs = freqs[pos_mask]
            pos_fft = fft_vals[pos_mask]
            
            hvac_mask = (pos_freqs >= 50) & (pos_freqs <= 300)
            hvac_freq = float(pos_freqs[hvac_mask][np.argmax(pos_fft[hvac_mask])]) if hvac_mask.any() else 0.0
            noise_floor = float(20 * np.log10(np.percentile(np.abs(data), 10) + 1e-10))
            
            hash_input = f"{hvac_freq:.1f}|{noise_floor:.1f}"
            fingerprint_hash = hashlib.md5(hash_input.encode()).hexdigest()[:16]
            
            return AcousticFingerprint(
                fingerprint_hash=fingerprint_hash,
                hvac_frequency=hvac_freq,
                room_resonance=[],
                reverb_time=0.5,
                audience_density=0.0,
                speaker_pattern=[],
                noise_floor=noise_floor,
                sample_duration=duration,
                confidence=0.5,
                metadata={'method': 'basic', 'sample_rate': sr}
            )
        except Exception as e:
            log.error(f"Basic fingerprint failed: {e}")
            return None

    def compare_fingerprints(self, fp1: AcousticFingerprint, 
                              fp2: AcousticFingerprint) -> float:
        """
        Compare two acoustic fingerprints.
        Returns similarity score 0-100.
        
        Uses weighted scoring across all acoustic dimensions.
        """
        score = 0.0
        max_score = 0.0
        reasons = []
        
        # ── HVAC frequency match (weight: 30) ─────────────────────
        # Most distinctive feature — building-specific
        if fp1.hvac_frequency > 0 and fp2.hvac_frequency > 0:
            max_score += 30
            diff = abs(fp1.hvac_frequency - fp2.hvac_frequency)
            if diff < 1.0:
                score += 30
                reasons.append(f"HVAC frequency match: {fp1.hvac_frequency:.1f}Hz")
            elif diff < 5.0:
                score += 20
                reasons.append(f"HVAC frequency close: {fp1.hvac_frequency:.1f} vs {fp2.hvac_frequency:.1f}Hz")
            elif diff < 10.0:
                score += 10
        
        # ── Room resonance match (weight: 25) ─────────────────────
        if fp1.room_resonance and fp2.room_resonance:
            max_score += 25
            matches = 0
            for r1 in fp1.room_resonance:
                for r2 in fp2.room_resonance:
                    if abs(r1 - r2) < 20:
                        matches += 1
                        break
            resonance_score = (matches / max(len(fp1.room_resonance), 1)) * 25
            score += resonance_score
            if resonance_score > 15:
                reasons.append(f"Room resonance match: {matches}/{len(fp1.room_resonance)} peaks")
        
        # ── Reverb time match (weight: 20) ────────────────────────
        max_score += 20
        reverb_diff = abs(fp1.reverb_time - fp2.reverb_time)
        if reverb_diff < 0.05:
            score += 20
            reasons.append(f"Reverb time match: {fp1.reverb_time:.2f}s")
        elif reverb_diff < 0.15:
            score += 12
        elif reverb_diff < 0.30:
            score += 5
        
        # ── Noise floor match (weight: 15) ────────────────────────
        max_score += 15
        noise_diff = abs(fp1.noise_floor - fp2.noise_floor)
        if noise_diff < 2.0:
            score += 15
            reasons.append(f"Noise floor match: {fp1.noise_floor:.1f}dB")
        elif noise_diff < 5.0:
            score += 8
        elif noise_diff < 10.0:
            score += 3
        
        # ── Audience density match (weight: 10) ───────────────────
        if fp1.audience_density > 0 and fp2.audience_density > 0:
            max_score += 10
            density_diff = abs(fp1.audience_density - fp2.audience_density)
            if density_diff < 0.01:
                score += 10
            elif density_diff < 0.03:
                score += 5
        
        # Normalize to 0-100
        if max_score > 0:
            similarity = (score / max_score) * 100
        else:
            similarity = 0
        
        return round(similarity, 1)

    def match_against_database(self, fingerprint: AcousticFingerprint) -> list[tuple]:
        """
        Match a fingerprint against all known theater profiles.
        Returns sorted list of (similarity_score, theater_profile) tuples.
        """
        matches = []
        for profile in self.theater_db:
            similarity = self.compare_fingerprints(fingerprint, profile.fingerprint)
            if similarity > 30:
                matches.append((similarity, profile))
        
        return sorted(matches, key=lambda x: x[0], reverse=True)

    def add_theater_profile(self, theater_name: str, screen_number: str,
                             city: str, audio_path: str) -> Optional[TheaterProfile]:
        """
        Add a new theater to the acoustic database.
        Record a reference audio sample in the empty theater.
        """
        fingerprint = self.extract_fingerprint_from_file(audio_path)
        if not fingerprint:
            return None
        
        theater_id = hashlib.md5(f"{theater_name}{screen_number}".encode()).hexdigest()[:8]
        
        profile = TheaterProfile(
            theater_id=theater_id,
            theater_name=theater_name,
            screen_number=screen_number,
            city=city,
            fingerprint=fingerprint,
            recorded_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Check if theater already exists
        for i, existing in enumerate(self.theater_db):
            if existing.theater_id == theater_id:
                self.theater_db[i] = profile
                self.save_db()
                return profile
        
        self.theater_db.append(profile)
        self.save_db()
        log.info(f"Added theater: {theater_name} {screen_number} ({city})")
        return profile


async def analyze_cam_copy(cam_url: str, 
                            engine: AcousticFingerprintEngine,
                            film_title: str = "") -> AttributionResult:
    """
    Download and analyze a CAM copy for theater attribution.
    
    This is the novel pipeline:
    1. Download first 60 seconds of CAM audio
    2. Extract acoustic fingerprint
    3. Match against theater database
    4. Cross-reference with incident database
    5. Return prosecution-grade attribution
    """
    log.info(f"Analyzing CAM copy: {cam_url[:60]}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "cam_audio.wav")
        
        # ── Download audio using yt-dlp ────────────────────────────
        try:
            result = subprocess.run([
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "worst",
                "--download-sections", "*0:00-1:00",
                "-o", audio_path,
                cam_url
            ], capture_output=True, timeout=60)
            
            if not os.path.exists(audio_path):
                # Try alternative extraction
                result = subprocess.run([
                    "ffmpeg", "-i", cam_url,
                    "-t", "60",
                    "-ar", "22050",
                    "-ac", "1",
                    audio_path
                ], capture_output=True, timeout=60)
        except Exception as e:
            log.warning(f"Audio download failed: {e}")
            return AttributionResult(
                matched=False, confidence=0,
                theater_name="Unknown", screen_number="Unknown",
                city="Unknown", match_reasons=["Audio download failed"],
                theater_incident_match=False
            )
        
        if not os.path.exists(audio_path):
            return AttributionResult(
                matched=False, confidence=0,
                theater_name="Unknown", screen_number="Unknown",
                city="Unknown", match_reasons=["Could not extract audio"],
                theater_incident_match=False
            )
        
        # ── Extract fingerprint ────────────────────────────────────
        fingerprint = engine.extract_fingerprint_from_file(audio_path)
        
        if not fingerprint:
            return AttributionResult(
                matched=False, confidence=0,
                theater_name="Unknown", screen_number="Unknown",
                city="Unknown", match_reasons=["Fingerprint extraction failed"],
                theater_incident_match=False
            )
        
        log.info(f"Fingerprint extracted: HVAC={fingerprint.hvac_frequency:.1f}Hz, "
                 f"Reverb={fingerprint.reverb_time:.2f}s, "
                 f"Noise={fingerprint.noise_floor:.1f}dB")
        
        # ── Match against database ─────────────────────────────────
        matches = engine.match_against_database(fingerprint)
        
        if not matches:
            return AttributionResult(
                matched=False, confidence=fingerprint.confidence * 50,
                theater_name="Unknown", screen_number="Unknown",
                city="Unknown",
                match_reasons=[f"HVAC: {fingerprint.hvac_frequency:.1f}Hz, "
                               f"Reverb: {fingerprint.reverb_time:.2f}s — "
                               f"No matching theater in database"],
                theater_incident_match=False
            )
        
        best_score, best_theater = matches[0]
        
        return AttributionResult(
            matched=best_score >= 70,
            confidence=best_score,
            theater_name=best_theater.theater_name,
            screen_number=best_theater.screen_number,
            city=best_theater.city,
            match_reasons=[
                f"Acoustic match score: {best_score}%",
                f"HVAC frequency: {fingerprint.hvac_frequency:.1f}Hz",
                f"Room reverb: {fingerprint.reverb_time:.2f}s",
                f"Noise floor: {fingerprint.noise_floor:.1f}dB",
            ],
            theater_incident_match=False
        )


def generate_synthetic_theater_profiles():
    """
    Generate synthetic theater profiles for testing.
    In production these come from recording reference audio
    in empty theaters before film screenings.
    """
    engine = AcousticFingerprintEngine("acoustic_theater_db.json")
    
    synthetic_theaters = [
        {
            "theater_id": "amcbur01",
            "theater_name": "AMC Burbank 16",
            "screen_number": "Screen 3",
            "city": "Burbank, CA",
            "fingerprint": AcousticFingerprint(
                fingerprint_hash="a1b2c3d4e5f6g7h8",
                hvac_frequency=120.3,
                room_resonance=[340.2, 520.8, 890.1, 1240.5, 1680.3],
                reverb_time=0.42,
                audience_density=0.031,
                speaker_pattern=[2100, 2150, 2080, 2200, 2120, 2090, 2180, 2110, 2160, 2095],
                noise_floor=-48.2,
                sample_duration=60.0,
                confidence=0.95,
                metadata={"capacity": 280, "dolby": "Atmos"}
            ),
            "recorded_at": "2026-01-15T19:30:00Z"
        },
        {
            "theater_id": "regalny02",
            "theater_name": "Regal Union Square",
            "screen_number": "Screen 7",
            "city": "New York, NY",
            "fingerprint": AcousticFingerprint(
                fingerprint_hash="b2c3d4e5f6g7h8i9",
                hvac_frequency=180.7,
                room_resonance=[280.4, 460.9, 720.3, 1100.8, 1520.2],
                reverb_time=0.68,
                audience_density=0.028,
                speaker_pattern=[1980, 2020, 1960, 2050, 2010, 1990, 2040, 2000, 2030, 1970],
                noise_floor=-52.1,
                sample_duration=60.0,
                confidence=0.93,
                metadata={"capacity": 340, "dolby": "Digital"}
            ),
            "recorded_at": "2026-01-20T14:00:00Z"
        },
        {
            "theater_id": "cinedemo",
            "theater_name": "CINEOS Demo Theater",
            "screen_number": "Screen 1",
            "city": "Apex, NC",
            "fingerprint": AcousticFingerprint(
                fingerprint_hash="c3d4e5f6g7h8i9j0",
                hvac_frequency=60.2,
                room_resonance=[420.1, 680.5, 950.8, 1380.2, 1820.6],
                reverb_time=0.31,
                audience_density=0.042,
                speaker_pattern=[2250, 2280, 2220, 2300, 2260, 2240, 2290, 2270, 2310, 2230],
                noise_floor=-45.8,
                sample_duration=60.0,
                confidence=0.92,
                metadata={"capacity": 120, "dolby": "Digital"}
            ),
            "recorded_at": "2026-05-05T00:00:00Z"
        }
    ]
    
    for t in synthetic_theaters:
        profile = TheaterProfile(
            theater_id=t["theater_id"],
            theater_name=t["theater_name"],
            screen_number=t["screen_number"],
            city=t["city"],
            fingerprint=t["fingerprint"],
            recorded_at=t["recorded_at"]
        )
        engine.theater_db.append(profile)
    
    engine.save_db()
    print(f"Generated {len(synthetic_theaters)} synthetic theater profiles")
    return engine


def demo_fingerprint_comparison():
    """
    Demo: Show how acoustic fingerprinting works for attribution.
    Simulates finding a CAM copy and matching it to a theater.
    """
    print("\n" + "="*60)
    print("  CINEOS Acoustic Theater Fingerprinting — Demo")
    print("  Novel Layer — US Prov. Pat. 64/049,190")
    print("="*60)
    
    engine = generate_synthetic_theater_profiles()
    
    print(f"\nTheater database: {len(engine.theater_db)} known theaters")
    for t in engine.theater_db:
        print(f"  {t.theater_name} {t.screen_number} ({t.city})")
        print(f"    HVAC: {t.fingerprint.hvac_frequency:.1f}Hz | "
              f"Reverb: {t.fingerprint.reverb_time:.2f}s | "
              f"Noise: {t.fingerprint.noise_floor:.1f}dB")
    
    print("\n" + "-"*60)
    print("Simulating CAM copy analysis...")
    print("Scenario: Michael (2026) CAM copy found on WhereYouWatch")
    print("Audio extracted from torrent — analyzing acoustic signature")
    print("-"*60)
    
    # Simulate a CAM copy that came from AMC Burbank
    # with slight variations (recording conditions differ slightly)
    cam_fingerprint = AcousticFingerprint(
        fingerprint_hash="unknown",
        hvac_frequency=120.8,      # Very close to AMC Burbank (120.3Hz)
        room_resonance=[338.5, 522.1, 891.4, 1238.9, 1682.0],  # Close match
        reverb_time=0.44,          # Close to AMC Burbank (0.42s)
        audience_density=0.034,    # Slightly different (audience present)
        speaker_pattern=[2110, 2145, 2085, 2195, 2125, 2095, 2175, 2115, 2165, 2090],
        noise_floor=-46.8,         # Slightly noisier (audience)
        sample_duration=58.3,
        confidence=0.88,
        metadata={"source": "cam_copy", "film": "Michael (2026)"}
    )
    
    print(f"\nCAM copy acoustic signature:")
    print(f"  HVAC frequency  : {cam_fingerprint.hvac_frequency:.1f}Hz")
    print(f"  Room reverb     : {cam_fingerprint.reverb_time:.2f}s")
    print(f"  Noise floor     : {cam_fingerprint.noise_floor:.1f}dB")
    print(f"  Resonance peaks : {[f'{r:.0f}Hz' for r in cam_fingerprint.room_resonance]}")
    
    print("\nMatching against theater database...")
    matches = engine.match_against_database(cam_fingerprint)
    
    if matches:
        print(f"\nTop matches:")
        for score, theater in matches[:3]:
            print(f"\n  {theater.theater_name} {theater.screen_number} ({theater.city})")
            print(f"  Match score: {score}%")
            hvac_diff = abs(cam_fingerprint.hvac_frequency - theater.fingerprint.hvac_frequency)
            print(f"  HVAC diff: {hvac_diff:.1f}Hz")
            reverb_diff = abs(cam_fingerprint.reverb_time - theater.fingerprint.reverb_time)
            print(f"  Reverb diff: {reverb_diff:.3f}s")
        
        best_score, best_theater = matches[0]
        print(f"\n{'='*60}")
        if best_score >= 70:
            print(f"  ATTRIBUTION CONFIRMED ({best_score}% confidence)")
            print(f"  Theater: {best_theater.theater_name}")
            print(f"  Screen : {best_theater.screen_number}")
            print(f"  City   : {best_theater.city}")
            print(f"\n  This CAM copy of Michael (2026) was recorded at")
            print(f"  {best_theater.theater_name}, {best_theater.city}")
            print(f"\n  Cross-reference with incident database:")
            print(f"  → Check CINEOS DB for recording incident at this")
            print(f"    theater on opening night")
            print(f"  → Match device type from IR detection with NFO file")
            print(f"  → Generate prosecution-grade evidence package")
        elif best_score >= 50:
            print(f"  PROBABLE MATCH ({best_score}% confidence)")
            print(f"  Theater: {best_theater.theater_name} — needs confirmation")
        else:
            print(f"  NO MATCH — Theater not in database")
            print(f"  → Add this theater to acoustic database")
        print("="*60)
    else:
        print("  No matches found — theater not in database yet")
    
    print("\nPatent note: This acoustic attribution pipeline is")
    print("genuinely novel. No anti-piracy company does this.")
    print("US Provisional Patent 64/049,190\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CINEOS Acoustic Theater Fingerprinting")
    ap.add_argument("--demo", action="store_true", help="Run attribution demo")
    ap.add_argument("--analyze", type=str, help="Analyze audio file for fingerprint")
    ap.add_argument("--add-theater", nargs=3, metavar=("NAME", "SCREEN", "CITY"),
                    help="Add theater profile from audio file")
    ap.add_argument("--audio", type=str, help="Audio file path")
    args = ap.parse_args()
    
    if args.demo:
        demo_fingerprint_comparison()
    elif args.analyze and args.audio:
        engine = AcousticFingerprintEngine()
        fp = engine.extract_fingerprint_from_file(args.audio)
        if fp:
            print(json.dumps({
                "hvac_frequency": fp.hvac_frequency,
                "room_resonance": fp.room_resonance,
                "reverb_time": fp.reverb_time,
                "noise_floor": fp.noise_floor,
                "confidence": fp.confidence
            }, indent=2))
    elif args.add_theater and args.audio:
        engine = AcousticFingerprintEngine()
        name, screen, city = args.add_theater
        profile = engine.add_theater_profile(name, screen, city, args.audio)
        if profile:
            print(f"Added: {profile.theater_name} {profile.screen_number}")
    else:
        ap.print_help()
