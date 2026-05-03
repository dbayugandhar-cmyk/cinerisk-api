import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet,
  Vibration, Animated, ScrollView, RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const API = 'https://cinerisk-api-production.up.railway.app';
const POLL_INTERVAL = 8000;

function timeAgo(iso) {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return Math.round(d) + 's ago';
  if (d < 3600) return Math.round(d/60) + 'm ago';
  return Math.round(d/3600) + 'h ago';
}
function confColor(c) { return c >= 0.8 ? '#ff3a3a' : c >= 0.5 ? '#ffb700' : '#00e676'; }

export default function StaffScreen() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeAlert, setActiveAlert] = useState(null);
  const [confirmed, setConfirmed] = useState(new Set());
  const [dismissed, setDismissed] = useState(new Set());
  const [theater, setTheater] = useState('Alamo Drafthouse');
  const [showReport, setShowReport] = useState(false);
  const [reportZone, setReportZone] = useState('');
  const [reportType, setReportType] = useState('PHONE');
  const [reportSubmitting, setReportSubmitting] = useState(false);
  const [reportSuccess, setReportSuccess] = useState(false);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const slideAnim = useRef(new Animated.Value(800)).current;
  const prevIds = useRef(new Set());

  const pulse = useCallback(() => {
    Animated.sequence([
      Animated.timing(pulseAnim, { toValue: 1.08, duration: 200, useNativeDriver: true }),
      Animated.timing(pulseAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
    ]).start();
  }, [pulseAnim]);

  const fetchIncidents = useCallback(async () => {
    try {
      const r = await fetch(API + '/theater/incidents?limit=200');
      const d = await r.json();
      const all = d.incidents || [];
      const now = Date.now();
      const recent = all.filter(i => {
        const age = (now - new Date(i.detected_at).getTime()) / 1000 / 60;
        return age < 30 && i.theater_name === theater;
      });
      const newOnes = recent.filter(i => !prevIds.current.has(i.id) && !dismissed.has(i.id));
      if (newOnes.length > 0) {
        Vibration.vibrate([0, 300, 100, 300]);
        pulse();
        setActiveAlert(newOnes[0]);
      }
      newOnes.forEach(i => prevIds.current.add(i.id));
      setIncidents(recent);
    } catch(e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  }, [theater, dismissed, pulse]);

  useEffect(() => {
    fetchIncidents();
    flushQueue(); // flush any offline queue on startup
    const interval = setInterval(fetchIncidents, POLL_INTERVAL);
    const flushInterval = setInterval(flushQueue, 60000); // retry queue every 60s
    return () => { clearInterval(interval); clearInterval(flushInterval); };
  }, [fetchIncidents]);

  function confirmAlert(incident) {
    setConfirmed(prev => new Set([...prev, incident.id]));
    setActiveAlert(null);
    Vibration.vibrate(100);
  }

  function dismissAlert(incident) {
    setDismissed(prev => new Set([...prev, incident.id]));
    setActiveAlert(null);
  }

  function openReport() {
    setShowReport(true);
    setReportZone('');
    setReportType('PHONE');
    setReportSuccess(false);
    Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 65, friction: 11 }).start();
  }

  function closeReport() {
    Animated.timing(slideAnim, { toValue: 800, duration: 250, useNativeDriver: true }).start(() => setShowReport(false));
  }

  async function saveToQueue(payload) {
    try {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      const existing = await AsyncStorage.getItem('cineos_offline_queue');
      const queue = existing ? JSON.parse(existing) : [];
      queue.push({ ...payload, queued_at: new Date().toISOString(), id: 'offline-' + Date.now() });
      await AsyncStorage.setItem('cineos_offline_queue', JSON.stringify(queue));
      console.log('[OFFLINE] Saved to queue:', queue.length, 'items');
      return queue.length;
    } catch(e) { console.error('[OFFLINE] Queue save error:', e); return 0; }
  }

  async function flushQueue() {
    try {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      const existing = await AsyncStorage.getItem('cineos_offline_queue');
      if (!existing) return;
      const queue = JSON.parse(existing);
      if (queue.length === 0) return;
      console.log('[OFFLINE] Flushing', queue.length, 'queued items');
      const remaining = [];
      for (const item of queue) {
        try {
          const r = await fetch(API + '/theater/incident', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': 'cineos-prod-2026-secure-key' },
            body: JSON.stringify(item),
          });
          const d = await r.json();
          if (d.status !== 'logged') remaining.push(item);
          else console.log('[OFFLINE] Flushed:', item.zone, 'zone');
        } catch(e) { remaining.push(item); }
      }
      await AsyncStorage.setItem('cineos_offline_queue', JSON.stringify(remaining));
      if (remaining.length < queue.length) {
        console.log('[OFFLINE] Flushed', queue.length - remaining.length, 'items,', remaining.length, 'remaining');
      }
    } catch(e) { console.error('[OFFLINE] Flush error:', e); }
  }

  async function submitReport() {
    if (!reportZone) return;
    setReportSubmitting(true);
    Vibration.vibrate(50);
    const payload = {
      theater_name: theater,
      screen_number: 'Screen 1',
      zone: reportZone,
      detection_type: reportType,
      confidence: 0.85,
      film_title: 'Unknown',
      device_id: 'cineos-staff-manual-' + Date.now(),
    };
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const r = await fetch(API + '/theater/incident', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': 'cineos-prod-2026-secure-key' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const d = await r.json();
      if (d.status === 'logged') {
        setReportSuccess(true);
        Vibration.vibrate([0, 100, 50, 100]);
        await flushQueue();
        setTimeout(() => closeReport(), 1500);
      } else { throw new Error('Bad response'); }
    } catch(e) {
      console.log('[OFFLINE] Network failed — saving to queue');
      const queueSize = await saveToQueue(payload);
      setReportSuccess(true);
      Vibration.vibrate([0, 50, 50, 50]);
      setTimeout(() => closeReport(), 1500);
    } finally { setReportSubmitting(false); }
  }

  const pendingCount = incidents.filter(i => !confirmed.has(i.id) && !dismissed.has(i.id)).length;

  if (loading) return (
    <SafeAreaView style={s.safe}>
      <View style={s.center}>
        <ActivityIndicator color="#ff3a3a" size="large" />
        <Text style={s.loadText}>CONNECTING...</Text>
      </View>
    </SafeAreaView>
  );

  if (activeAlert) {
    const conf = Math.round(activeAlert.confidence * 100);
    return (
      <SafeAreaView style={s.safe}>
        <Animated.View style={[s.alertScreen, { transform: [{ scale: pulseAnim }] }]}>
          <View style={s.alertHeader}>
            <Text style={s.alertHeaderText}>RECORDING DETECTED</Text>
            <Text style={s.alertTime}>{timeAgo(activeAlert.detected_at)}</Text>
          </View>
          <View style={s.alertBody}>
            <Text style={s.alertFilm}>{activeAlert.film_title}</Text>
            <Text style={s.alertScreen2}>{activeAlert.screen_number}</Text>
            <View style={s.seatMap}>
              <Text style={s.screenBar}>SCREEN</Text>
              <View style={s.zoneRow}>
                {['LEFT', 'CENTER', 'RIGHT'].map(z => (
                  <View key={z} style={[s.zoneBox, activeAlert.zone === z && s.zoneBoxActive]}>
                    <Text style={[s.zoneBoxText, activeAlert.zone === z && s.zoneBoxTextActive]}>
                      {z === 'LEFT' ? '<<' : z === 'CENTER' ? 'O' : '>>'}
                    </Text>
                    <Text style={[s.zoneBoxLabel, activeAlert.zone === z && s.zoneBoxTextActive]}>{z}</Text>
                    {activeAlert.zone === z && <Text style={s.zoneBoxConf}>{conf}%</Text>}
                  </View>
                ))}
              </View>
              {activeAlert.seat_location && <Text style={s.seatLabel}>{activeAlert.seat_location}</Text>}
            </View>
            <Text style={s.alertInstruction}>
              Check {activeAlert.zone} zone. Look for phone held horizontal pointed at screen.
            </Text>
          </View>
          <View style={s.alertActions}>
            <TouchableOpacity style={s.dismissBtn} onPress={() => dismissAlert(activeAlert)} activeOpacity={0.8}>
              <Text style={s.dismissText}>FALSE ALARM</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.confirmBtn} onPress={() => confirmAlert(activeAlert)} activeOpacity={0.8}>
              <Text style={s.confirmText}>CONFIRMED</Text>
            </TouchableOpacity>
          </View>
        </Animated.View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchIncidents(); }} tintColor="#ff3a3a" />}>
        <View style={s.header}>
          <View>
            <Text style={s.logo}>CINEOS</Text>
            <Text style={s.headerSub}>STAFF MONITOR</Text>
          </View>
          {pendingCount > 0
            ? <View style={s.alertBadge}><Text style={s.alertBadgeText}>{pendingCount} ALERTS</Text></View>
            : <View style={s.clearBadge}><Text style={s.clearBadgeText}>ALL CLEAR</Text></View>
          }
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.theaterScroll}>
          {['Alamo Drafthouse','Demo Theater','AMC Empire 25','Regal LA Live','Cinemark Houston'].map(t => (
            <TouchableOpacity key={t} style={[s.theaterChip, theater === t && s.theaterChipActive]} onPress={() => setTheater(t)}>
              <Text style={[s.theaterChipText, theater === t && {color:'#ff3a3a'}]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {incidents.length === 0 ? (
          <View style={s.clearScreen}>
            <Text style={s.clearIcon}>shield</Text>
            <Text style={s.clearTitle}>ALL CLEAR</Text>
            <Text style={s.clearSub}>No incidents in the last 30 minutes</Text>
          </View>
        ) : (
          <View>
            <Text style={s.sectionLabel}>RECENT - LAST 30 MIN</Text>
            {incidents.map(inc => {
              const isConfirmed = confirmed.has(inc.id);
              const isDismissed = dismissed.has(inc.id);
              return (
                <TouchableOpacity
                  key={inc.id}
                  style={[s.incCard, isConfirmed && s.incCardConfirmed, isDismissed && s.incCardDismissed]}
                  onPress={() => !isConfirmed && !isDismissed && setActiveAlert(inc)}
                  activeOpacity={0.8}>
                  <View style={{flex:1}}>
                    <Text style={[s.incZone, {color: confColor(inc.confidence)}]}>{inc.zone}</Text>
                    <Text style={s.incMeta}>{inc.screen_number} - {timeAgo(inc.detected_at)}</Text>
                    {inc.seat_location && <Text style={s.incSeat}>{inc.seat_location}</Text>}
                  </View>
                  <View style={{alignItems:'flex-end', gap:4}}>
                    <Text style={[s.incConf, {color: confColor(inc.confidence)}]}>{Math.round(inc.confidence*100)}%</Text>
                    {isConfirmed && <Text style={s.statusConfirmed}>CONFIRMED</Text>}
                    {isDismissed && <Text style={s.statusDismissed}>DISMISSED</Text>}
                    {!isConfirmed && !isDismissed && <Text style={s.statusPending}>TAP</Text>}
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        <Text style={s.footer}>Auto-refreshes every 8s - {theater}</Text>
        <Text style={s.privacyNotice}>
          CINEOS monitors recording devices, not individuals. No video, facial recognition, or biometric data is collected. Zone detection only. US Prov. Pat. 64/049,190
        </Text>
      </ScrollView>

      <TouchableOpacity style={s.fab} onPress={openReport} activeOpacity={0.85}>
        <Text style={s.fabText}>+ REPORT</Text>
      </TouchableOpacity>

      {showReport && (
        <View style={s.overlay}>
          <TouchableOpacity style={s.overlayBg} onPress={closeReport} activeOpacity={1} />
          <Animated.View style={[s.sheet, {transform:[{translateY: slideAnim}]}]}>
            <View style={s.sheetHandle} />
            <Text style={s.sheetTitle}>MANUAL REPORT</Text>
            <Text style={s.sheetSub}>{theater}</Text>

            <Text style={s.sheetLabel}>ZONE</Text>
            <View style={s.sheetZoneRow}>
              {['LEFT','CENTER','RIGHT'].map(z => (
                <TouchableOpacity key={z} style={[s.sheetZoneBtn, reportZone === z && s.sheetZoneBtnOn]} onPress={() => setReportZone(z)} activeOpacity={0.8}>
                  <Text style={s.sheetZoneIcon}>{z === 'LEFT' ? '<<' : z === 'CENTER' ? 'O' : '>>'}</Text>
                  <Text style={[s.sheetZoneText, reportZone === z && {color:'#ff3a3a'}]}>{z}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.sheetLabel}>WHAT DID YOU SEE?</Text>
            <View style={s.sheetTypeRow}>
              {[{id:'PHONE',icon:'Phone',label:'Phone'},{id:'CAMCORDER',icon:'Cam',label:'Camcorder'},{id:'SILENT',icon:'Eye',label:'Silent'},{id:'SUSPICIOUS',icon:'Warn',label:'Suspicious'}].map(t => (
                <TouchableOpacity key={t.id} style={[s.sheetTypeBtn, reportType === t.id && s.sheetTypeBtnOn]} onPress={() => setReportType(t.id)} activeOpacity={0.8}>
                  <Text style={s.sheetTypeIcon}>{t.icon}</Text>
                  <Text style={[s.sheetTypeText, reportType === t.id && {color:'#ffb700'}]}>{t.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {reportSuccess ? (
              <View style={s.sheetSuccess}>
                <Text style={s.sheetSuccessText}>REPORTED</Text>
              </View>
            ) : (
              <TouchableOpacity style={[s.sheetSubmit, !reportZone && {opacity:0.4}]} onPress={submitReport} disabled={!reportZone || reportSubmitting} activeOpacity={0.85}>
                {reportSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.sheetSubmitText}>SUBMIT REPORT</Text>}
              </TouchableOpacity>
            )}
          </Animated.View>
        </View>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:{flex:1,backgroundColor:'#06080b'},
  center:{flex:1,alignItems:'center',justifyContent:'center',gap:12},
  loadText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)',letterSpacing:2},
  alertScreen:{flex:1,backgroundColor:'#0d0608'},
  alertHeader:{backgroundColor:'#ff3a3a',padding:20,paddingTop:60,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},
  alertHeaderText:{fontFamily:'SpaceMono',fontSize:14,color:'#fff',letterSpacing:1.5,fontWeight:'700'},
  alertTime:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.8)'},
  alertBody:{flex:1,padding:24},
  alertFilm:{fontFamily:'SpaceMono',fontSize:22,color:'#fff',letterSpacing:1,marginBottom:4},
  alertScreen2:{fontFamily:'SpaceMono',fontSize:12,color:'rgba(255,255,255,0.5)',marginBottom:24},
  seatMap:{backgroundColor:'#0e1216',borderRadius:12,padding:20,marginBottom:24,borderWidth:1,borderColor:'rgba(255,58,58,0.3)'},
  screenBar:{fontFamily:'SpaceMono',fontSize:10,color:'#2eb8ff',textAlign:'center',marginBottom:16,letterSpacing:1},
  zoneRow:{flexDirection:'row',gap:8,marginBottom:12},
  zoneBox:{flex:1,padding:14,borderRadius:8,borderWidth:1,borderColor:'rgba(255,255,255,0.08)',backgroundColor:'#13181e',alignItems:'center',gap:4},
  zoneBoxActive:{borderColor:'#ff3a3a',backgroundColor:'rgba(255,58,58,0.2)'},
  zoneBoxText:{fontSize:18,color:'rgba(255,255,255,0.3)'},
  zoneBoxTextActive:{color:'#ff3a3a'},
  zoneBoxLabel:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.3)',letterSpacing:1},
  zoneBoxConf:{fontFamily:'SpaceMono',fontSize:14,color:'#ff3a3a',fontWeight:'700'},
  seatLabel:{fontFamily:'SpaceMono',fontSize:11,color:'#ffb700',textAlign:'center'},
  alertInstruction:{fontFamily:'SpaceMono',fontSize:13,color:'rgba(255,255,255,0.6)',textAlign:'center',lineHeight:24},
  alertActions:{flexDirection:'row',padding:20,gap:12},
  dismissBtn:{flex:1,padding:18,backgroundColor:'#13181e',borderRadius:12,borderWidth:1,borderColor:'rgba(255,255,255,0.15)',alignItems:'center'},
  dismissText:{fontFamily:'SpaceMono',fontSize:13,color:'rgba(255,255,255,0.6)',letterSpacing:1},
  confirmBtn:{flex:2,padding:18,backgroundColor:'#ff3a3a',borderRadius:12,alignItems:'center'},
  confirmText:{fontFamily:'SpaceMono',fontSize:13,color:'#fff',letterSpacing:1,fontWeight:'700'},
  header:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingHorizontal:20,paddingVertical:14,borderBottomWidth:1,borderBottomColor:'rgba(255,255,255,0.08)'},
  logo:{fontFamily:'SpaceMono',fontSize:18,color:'#fff',letterSpacing:2},
  headerSub:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:2,marginTop:2},
  alertBadge:{backgroundColor:'rgba(255,58,58,0.15)',borderWidth:1,borderColor:'rgba(255,58,58,0.4)',paddingHorizontal:12,paddingVertical:6,borderRadius:20},
  alertBadgeText:{fontFamily:'SpaceMono',fontSize:10,color:'#ff3a3a',letterSpacing:1.5},
  clearBadge:{backgroundColor:'rgba(0,230,118,0.1)',borderWidth:1,borderColor:'rgba(0,230,118,0.3)',paddingHorizontal:12,paddingVertical:6,borderRadius:20},
  clearBadgeText:{fontFamily:'SpaceMono',fontSize:10,color:'#00e676',letterSpacing:1},
  theaterScroll:{paddingHorizontal:20,paddingVertical:12},
  theaterChip:{paddingHorizontal:14,paddingVertical:8,borderRadius:20,borderWidth:1,borderColor:'rgba(255,255,255,0.08)',backgroundColor:'#0e1216',marginRight:8},
  theaterChipActive:{borderColor:'rgba(255,58,58,0.4)',backgroundColor:'rgba(255,58,58,0.08)'},
  theaterChipText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.5)',letterSpacing:0.5},
  clearScreen:{alignItems:'center',paddingVertical:80,gap:12},
  clearIcon:{fontSize:48},
  clearTitle:{fontFamily:'SpaceMono',fontSize:24,color:'#00e676',letterSpacing:3},
  clearSub:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.3)',letterSpacing:1},
  sectionLabel:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.3)',letterSpacing:2,paddingHorizontal:20,marginBottom:8,marginTop:12},
  incCard:{marginHorizontal:20,marginBottom:8,backgroundColor:'#0e1216',borderWidth:1,borderColor:'rgba(255,58,58,0.2)',borderRadius:10,padding:14,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},
  incCardConfirmed:{borderColor:'rgba(0,230,118,0.2)',backgroundColor:'rgba(0,230,118,0.04)'},
  incCardDismissed:{borderColor:'rgba(255,255,255,0.05)',opacity:0.4},
  incZone:{fontFamily:'SpaceMono',fontSize:14,letterSpacing:1,marginBottom:4},
  incMeta:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)'},
  incSeat:{fontFamily:'SpaceMono',fontSize:10,color:'#ffb700',marginTop:2},
  incConf:{fontFamily:'SpaceMono',fontSize:20},
  statusConfirmed:{fontFamily:'SpaceMono',fontSize:8,color:'#00e676',letterSpacing:1},
  statusDismissed:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.3)',letterSpacing:1},
  statusPending:{fontFamily:'SpaceMono',fontSize:8,color:'#ffb700',letterSpacing:1},
  footer:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.2)',textAlign:'center',marginTop:20,paddingBottom:100,letterSpacing:1},
  privacyNotice:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.15)',textAlign:'center',paddingHorizontal:20,paddingBottom:20,lineHeight:14,letterSpacing:0.5},
  fab:{position:'absolute',bottom:100,right:20,backgroundColor:'#ff3a3a',paddingHorizontal:18,paddingVertical:12,borderRadius:24,elevation:5,shadowColor:'#ff3a3a',shadowOffset:{width:0,height:4},shadowOpacity:0.4,shadowRadius:8},
  fabText:{fontFamily:'SpaceMono',fontSize:11,color:'#fff',letterSpacing:1.5},
  overlay:{position:'absolute',top:0,left:0,right:0,bottom:0},
  overlayBg:{position:'absolute',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.6)'},
  sheet:{position:'absolute',bottom:0,left:0,right:0,backgroundColor:'#0e1216',borderTopLeftRadius:20,borderTopRightRadius:20,padding:24,paddingBottom:40,borderTopWidth:1,borderTopColor:'rgba(255,255,255,0.1)'},
  sheetHandle:{width:40,height:4,backgroundColor:'rgba(255,255,255,0.2)',borderRadius:2,alignSelf:'center',marginBottom:20},
  sheetTitle:{fontFamily:'SpaceMono',fontSize:16,color:'#fff',letterSpacing:2,marginBottom:4},
  sheetSub:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)',letterSpacing:1.5,marginBottom:20},
  sheetLabel:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:2,marginBottom:10},
  sheetZoneRow:{flexDirection:'row',gap:10,marginBottom:20},
  sheetZoneBtn:{flex:1,paddingVertical:16,borderWidth:1,borderColor:'rgba(255,255,255,0.08)',backgroundColor:'#13181e',borderRadius:10,alignItems:'center',gap:6},
  sheetZoneBtnOn:{borderColor:'#ff3a3a',backgroundColor:'rgba(255,58,58,0.15)'},
  sheetZoneIcon:{fontSize:16,color:'#fff'},
  sheetZoneText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.5)',letterSpacing:1},
  sheetTypeRow:{flexDirection:'row',flexWrap:'wrap',gap:8,marginBottom:24},
  sheetTypeBtn:{width:'47%',paddingVertical:12,borderWidth:1,borderColor:'rgba(255,255,255,0.08)',backgroundColor:'#13181e',borderRadius:8,alignItems:'center',gap:4},
  sheetTypeBtnOn:{borderColor:'#ffb700',backgroundColor:'rgba(255,183,0,0.12)'},
  sheetTypeIcon:{fontSize:14,color:'#fff'},
  sheetTypeText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.5)'},
  sheetSubmit:{backgroundColor:'#ff3a3a',padding:18,borderRadius:12,alignItems:'center'},
  sheetSubmitText:{fontFamily:'SpaceMono',fontSize:14,color:'#fff',letterSpacing:1.5},
  sheetSuccess:{backgroundColor:'rgba(0,230,118,0.12)',borderWidth:1,borderColor:'rgba(0,230,118,0.3)',padding:18,borderRadius:12,alignItems:'center'},
  sheetSuccessText:{fontFamily:'SpaceMono',fontSize:14,color:'#00e676',letterSpacing:2},
});
