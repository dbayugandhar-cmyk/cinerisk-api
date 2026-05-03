import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet,
  Vibration, Animated, ScrollView, RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const API = 'https://cinerisk-api-production.up.railway.app';
const POLL_INTERVAL = 8000;

interface Incident {
  id: string;
  theater_name: string;
  screen_number: string;
  zone: string;
  confidence: number;
  film_title: string;
  alerted: boolean;
  detected_at: string;
  seat_location: string | null;
  detection_type: string;
}

function timeAgo(iso: string) {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return `${Math.round(d)}s ago`;
  if (d < 3600) return `${Math.round(d / 60)}m ago`;
  return `${Math.round(d / 3600)}h ago`;
}

function confColor(c: number) {
  return c >= 0.8 ? '#ff3a3a' : c >= 0.5 ? '#ffb700' : '#00e676';
}

export default function StaffScreen() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeAlert, setActiveAlert] = useState<Incident | null>(null);
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [theater, setTheater] = useState('Demo Theater');
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const prevIds = useRef<Set<string>>(new Set());

  const pulse = useCallback(() => {
    Animated.sequence([
      Animated.timing(pulseAnim, { toValue: 1.08, duration: 200, useNativeDriver: true }),
      Animated.timing(pulseAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
    ]).start();
  }, [pulseAnim]);

  const fetchIncidents = useCallback(async () => {
    try {
      const r = await fetch(`${API}/theater/incidents?limit=200`);
      const d = await r.json();
      const all: Incident[] = d.incidents || [];

      // Filter to this theater and last 30 minutes only
      const now = Date.now();
      const recent = all.filter(i => {
        const age = (now - new Date(i.detected_at).getTime()) / 1000 / 60;
        return age < 30 && i.theater_name === theater;
      });

      // Check for new incidents
      const newOnes = recent.filter(i => !prevIds.current.has(i.id) && !dismissed.has(i.id));
      if (newOnes.length > 0) {
        Vibration.vibrate([0, 300, 100, 300]);
        pulse();
        setActiveAlert(newOnes[0]);
      }

      newOnes.forEach(i => prevIds.current.add(i.id));
      setIncidents(recent);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [theater, dismissed, pulse]);

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchIncidents]);

  function confirmAlert(incident: Incident) {
    setConfirmed(prev => new Set([...prev, incident.id]));
    setActiveAlert(null);
    Vibration.vibrate(100);
  }

  function dismissAlert(incident: Incident) {
    setDismissed(prev => new Set([...prev, incident.id]));
    setActiveAlert(null);
  }

  const pendingCount = incidents.filter(i =>
    !confirmed.has(i.id) && !dismissed.has(i.id)
  ).length;

  if (loading) return (
    <SafeAreaView style={s.safe}>
      <View style={s.center}>
        <ActivityIndicator color="#ff3a3a" size="large" />
        <Text style={s.loadText}>CONNECTING...</Text>
      </View>
    </SafeAreaView>
  );

  // ACTIVE ALERT — full screen takeover
  if (activeAlert) {
    const conf = Math.round(activeAlert.confidence * 100);
    return (
      <SafeAreaView style={s.safe}>
        <Animated.View style={[s.alertScreen, { transform: [{ scale: pulseAnim }] }]}>

          <View style={s.alertHeader}>
            <Text style={s.alertHeaderText}>⚠ RECORDING DETECTED</Text>
            <Text style={s.alertTime}>{timeAgo(activeAlert.detected_at)}</Text>
          </View>

          <View style={s.alertBody}>
            <Text style={s.alertFilm}>{activeAlert.film_title}</Text>
            <Text style={s.alertScreen2}>{activeAlert.screen_number}</Text>

            {/* Seat map */}
            <View style={s.seatMap}>
              <Text style={s.screenBar}>◀ ─── SCREEN ─── ▶</Text>
              <View style={s.zoneRow}>
                {['LEFT', 'CENTER', 'RIGHT'].map(z => (
                  <View key={z} style={[
                    s.zoneBox,
                    activeAlert.zone === z && s.zoneBoxActive
                  ]}>
                    <Text style={[s.zoneBoxText, activeAlert.zone === z && s.zoneBoxTextActive]}>
                      {z === 'LEFT' ? '◀' : z === 'CENTER' ? '●' : '▶'}
                    </Text>
                    <Text style={[s.zoneBoxLabel, activeAlert.zone === z && s.zoneBoxTextActive]}>
                      {z}
                    </Text>
                    {activeAlert.zone === z && (
                      <Text style={s.zoneBoxConf}>{conf}%</Text>
                    )}
                  </View>
                ))}
              </View>
              {activeAlert.seat_location && (
                <Text style={s.seatLabel}>📍 {activeAlert.seat_location}</Text>
              )}
            </View>

            <Text style={s.alertInstruction}>
              Check {activeAlert.zone} zone{'\n'}
              Look for phone held horizontally{'\n'}
              pointed at screen
            </Text>
          </View>

          <View style={s.alertActions}>
            <TouchableOpacity
              style={s.dismissBtn}
              onPress={() => dismissAlert(activeAlert)}
              activeOpacity={0.8}>
              <Text style={s.dismissText}>✕  FALSE ALARM</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={s.confirmBtn}
              onPress={() => confirmAlert(activeAlert)}
              activeOpacity={0.8}>
              <Text style={s.confirmText}>✓  CONFIRMED</Text>
            </TouchableOpacity>
          </View>

          <Text style={s.alertFooter}>
            CINEOS · US Prov. Pat. 64/049,190
          </Text>
        </Animated.View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchIncidents(); }} tintColor="#ff3a3a" />
        }>

        <View style={s.header}>
          <View>
            <Text style={s.logo}>CINE<Text style={{ color: '#ff3a3a' }}>OS</Text></Text>
            <Text style={s.headerSub}>STAFF MONITOR</Text>
          </View>
          {pendingCount > 0 ? (
            <View style={s.alertBadge}>
              <Text style={s.alertBadgeText}>{pendingCount} ALERT{pendingCount > 1 ? 'S' : ''}</Text>
            </View>
          ) : (
            <View style={s.clearBadge}>
              <Text style={s.clearBadgeText}>● ALL CLEAR</Text>
            </View>
          )}
        </View>

        {/* Theater selector */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.theaterScroll}>
          {['Demo Theater', 'Alamo Drafthouse', 'AMC Empire 25', 'Regal LA Live', 'Cinemark Houston'].map(t => (
            <TouchableOpacity
              key={t}
              style={[s.theaterChip, theater === t && s.theaterChipActive]}
              onPress={() => setTheater(t)}>
              <Text style={[s.theaterChipText, theater === t && { color: '#ff3a3a' }]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {incidents.length === 0 ? (
          <View style={s.clearScreen}>
            <Text style={s.clearIcon}>🛡️</Text>
            <Text style={s.clearTitle}>ALL CLEAR</Text>
            <Text style={s.clearSub}>No incidents in the last 30 minutes</Text>
            <Text style={s.clearSub}>Pull down to refresh</Text>
          </View>
        ) : (
          <View style={s.incidentList}>
            <Text style={s.sectionLabel}>RECENT — LAST 30 MIN</Text>
            {incidents.map(inc => {
              const isConfirmed = confirmed.has(inc.id);
              const isDismissed = dismissed.has(inc.id);
              return (
                <TouchableOpacity
                  key={inc.id}
                  style={[
                    s.incCard,
                    isConfirmed && s.incCardConfirmed,
                    isDismissed && s.incCardDismissed,
                  ]}
                  onPress={() => !isConfirmed && !isDismissed && setActiveAlert(inc)}
                  activeOpacity={0.8}>
                  <View style={s.incLeft}>
                    <Text style={[s.incZone, { color: confColor(inc.confidence) }]}>
                      {inc.zone === 'LEFT' ? '◀' : inc.zone === 'CENTER' ? '●' : '▶'} {inc.zone}
                    </Text>
                    <Text style={s.incMeta}>{inc.screen_number} · {timeAgo(inc.detected_at)}</Text>
                    {inc.seat_location && <Text style={s.incSeat}>📍 {inc.seat_location}</Text>}
                  </View>
                  <View style={s.incRight}>
                    <Text style={[s.incConf, { color: confColor(inc.confidence) }]}>
                      {Math.round(inc.confidence * 100)}%
                    </Text>
                    {isConfirmed && <Text style={s.statusConfirmed}>CONFIRMED</Text>}
                    {isDismissed && <Text style={s.statusDismissed}>DISMISSED</Text>}
                    {!isConfirmed && !isDismissed && <Text style={s.statusPending}>TAP</Text>}
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        <Text style={s.footer}>
          Auto-refreshes every 8s · {theater}{'\n'}
          CINEOS · US Prov. Pat. 64/049,190
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#06080b' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadText: { fontFamily: 'SpaceMono', fontSize: 10, color: 'rgba(255,255,255,0.4)', letterSpacing: 2 },

  // Alert screen
  alertScreen: { flex: 1, backgroundColor: '#0d0608' },
  alertHeader: { backgroundColor: '#ff3a3a', padding: 20, paddingTop: 60, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  alertHeaderText: { fontFamily: 'SpaceMono', fontSize: 14, color: '#fff', letterSpacing: 1.5, fontWeight: '700' },
  alertTime: { fontFamily: 'SpaceMono', fontSize: 10, color: 'rgba(255,255,255,0.8)' },
  alertBody: { flex: 1, padding: 24 },
  alertFilm: { fontFamily: 'SpaceMono', fontSize: 22, color: '#fff', letterSpacing: 1, marginBottom: 4 },
  alertScreen2: { fontFamily: 'SpaceMono', fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 24 },
  seatMap: { backgroundColor: '#0e1216', borderRadius: 12, padding: 20, marginBottom: 24, borderWidth: 1, borderColor: 'rgba(255,58,58,0.3)' },
  screenBar: { fontFamily: 'SpaceMono', fontSize: 10, color: '#2eb8ff', textAlign: 'center', marginBottom: 16, letterSpacing: 1 },
  zoneRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  zoneBox: { flex: 1, padding: 14, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', backgroundColor: '#13181e', alignItems: 'center', gap: 4 },
  zoneBoxActive: { borderColor: '#ff3a3a', backgroundColor: 'rgba(255,58,58,0.2)' },
  zoneBoxText: { fontSize: 20, color: 'rgba(255,255,255,0.3)' },
  zoneBoxTextActive: { color: '#ff3a3a' },
  zoneBoxLabel: { fontFamily: 'SpaceMono', fontSize: 9, color: 'rgba(255,255,255,0.3)', letterSpacing: 1 },
  zoneBoxConf: { fontFamily: 'SpaceMono', fontSize: 14, color: '#ff3a3a', fontWeight: '700' },
  seatLabel: { fontFamily: 'SpaceMono', fontSize: 11, color: '#ffb700', textAlign: 'center' },
  alertInstruction: { fontFamily: 'SpaceMono', fontSize: 13, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 24, letterSpacing: 0.5 },
  alertActions: { flexDirection: 'row', padding: 20, gap: 12 },
  dismissBtn: { flex: 1, padding: 18, backgroundColor: '#13181e', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)', alignItems: 'center' },
  dismissText: { fontFamily: 'SpaceMono', fontSize: 13, color: 'rgba(255,255,255,0.6)', letterSpacing: 1 },
  confirmBtn: { flex: 2, padding: 18, backgroundColor: '#ff3a3a', borderRadius: 12, alignItems: 'center' },
  confirmText: { fontFamily: 'SpaceMono', fontSize: 13, color: '#fff', letterSpacing: 1, fontWeight: '700' },
  alertFooter: { fontFamily: 'SpaceMono', fontSize: 9, color: 'rgba(255,255,255,0.2)', textAlign: 'center', paddingBottom: 20, letterSpacing: 1 },

  // Normal screen
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.08)' },
  logo: { fontFamily: 'SpaceMono', fontSize: 18, color: '#fff', letterSpacing: 2 },
  headerSub: { fontFamily: 'SpaceMono', fontSize: 9, color: 'rgba(255,255,255,0.4)', letterSpacing: 2, marginTop: 2 },
  alertBadge: { backgroundColor: 'rgba(255,58,58,0.15)', borderWidth: 1, borderColor: 'rgba(255,58,58,0.4)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20 },
  alertBadgeText: { fontFamily: 'SpaceMono', fontSize: 10, color: '#ff3a3a', letterSpacing: 1.5 },
  clearBadge: { backgroundColor: 'rgba(0,230,118,0.1)', borderWidth: 1, borderColor: 'rgba(0,230,118,0.3)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20 },
  clearBadgeText: { fontFamily: 'SpaceMono', fontSize: 10, color: '#00e676', letterSpacing: 1 },
  theaterScroll: { paddingHorizontal: 20, paddingVertical: 12 },
  theaterChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', backgroundColor: '#0e1216', marginRight: 8 },
  theaterChipActive: { borderColor: 'rgba(255,58,58,0.4)', backgroundColor: 'rgba(255,58,58,0.08)' },
  theaterChipText: { fontFamily: 'SpaceMono', fontSize: 10, color: 'rgba(255,255,255,0.5)', letterSpacing: 0.5 },
  clearScreen: { alignItems: 'center', paddingVertical: 80, gap: 12 },
  clearIcon: { fontSize: 48 },
  clearTitle: { fontFamily: 'SpaceMono', fontSize: 24, color: '#00e676', letterSpacing: 3 },
  clearSub: { fontFamily: 'SpaceMono', fontSize: 10, color: 'rgba(255,255,255,0.3)', letterSpacing: 1 },
  sectionLabel: { fontFamily: 'SpaceMono', fontSize: 9, color: 'rgba(255,255,255,0.3)', letterSpacing: 2, paddingHorizontal: 20, marginBottom: 8 },
  incidentList: { paddingTop: 12 },
  incCard: { marginHorizontal: 20, marginBottom: 8, backgroundColor: '#0e1216', borderWidth: 1, borderColor: 'rgba(255,58,58,0.2)', borderRadius: 10, padding: 14, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  incCardConfirmed: { borderColor: 'rgba(0,230,118,0.2)', backgroundColor: 'rgba(0,230,118,0.04)' },
  incCardDismissed: { borderColor: 'rgba(255,255,255,0.05)', opacity: 0.4 },
  incLeft: { flex: 1 },
  incRight: { alignItems: 'flex-end', gap: 4 },
  incZone: { fontFamily: 'SpaceMono', fontSize: 14, letterSpacing: 1, marginBottom: 4 },
  incMeta: { fontFamily: 'SpaceMono', fontSize: 10, color: 'rgba(255,255,255,0.4)' },
  incSeat: { fontFamily: 'SpaceMono', fontSize: 10, color: '#ffb700', marginTop: 2 },
  incConf: { fontFamily: 'SpaceMono', fontSize: 20 },
  statusConfirmed: { fontFamily: 'SpaceMono', fontSize: 8, color: '#00e676', letterSpacing: 1 },
  statusDismissed: { fontFamily: 'SpaceMono', fontSize: 8, color: 'rgba(255,255,255,0.3)', letterSpacing: 1 },
  statusPending: { fontFamily: 'SpaceMono', fontSize: 8, color: '#ffb700', letterSpacing: 1 },
  footer: { fontFamily: 'SpaceMono', fontSize: 9, color: 'rgba(255,255,255,0.2)', textAlign: 'center', marginTop: 20, paddingBottom: 30, lineHeight: 18, letterSpacing: 1 },
});
