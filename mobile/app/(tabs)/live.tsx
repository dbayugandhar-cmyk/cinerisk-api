import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const API = 'https://cinerisk-api-production.up.railway.app';

function timeAgo(iso) {
  const d = (Date.now() - new Date(iso).getTime()) / 1000;
  if (d < 60) return Math.round(d) + 's ago';
  if (d < 3600) return Math.round(d/60) + 'm ago';
  return Math.round(d/3600) + 'h ago';
}

function confColor(c) { return c >= 0.8 ? '#ff3a3a' : c >= 0.5 ? '#ffb700' : '#00e676'; }

export default function LiveScreen() {
  const [incidents, setIncidents] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const [ir, sr] = await Promise.all([
        fetch(API + '/theater/incidents?limit=200'),
        fetch(API + '/theater/stats'),
      ]);
      const id = await ir.json();
      const sd = await sr.json();
      setIncidents(id.incidents || []);
      setStats(sd);
      setLastUpdated(new Date().toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}));
    } catch(e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { fetchData(); const i = setInterval(fetchData, 15000); return () => clearInterval(i); }, []);

  if (loading) return (
    <SafeAreaView style={s.safe}>
      <View style={s.center}>
        <ActivityIndicator color="#ff3a3a" size="large" />
        <Text style={s.loadText}>CONNECTING TO RAILWAY...</Text>
      </View>
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} tintColor="#ff3a3a" />}>
        <View style={s.header}>
          <View>
            <Text style={s.logo}>CINEOS</Text>
            <Text style={s.sub}>LIVE INCIDENT FEED</Text>
          </View>
          <View style={s.pill}><View style={s.dot} /><Text style={s.pillText}>LIVE</Text></View>
        </View>

        {stats && (
          <View style={s.statsRow}>
            {[
              {val: stats.total_incidents, label: 'INCIDENTS', color: '#ff3a3a'},
              {val: stats.theaters_active, label: 'THEATERS', color: '#ffb700'},
              {val: Math.round((stats.avg_confidence||0)*100)+'%', label: 'AVG CONF', color: '#00e676'},
              {val: stats.compliance_score, label: 'COMPLIANCE', color: '#2eb8ff'},
            ].map(item => (
              <View key={item.label} style={s.statCard}>
                <Text style={[s.statVal, {color: item.color}]}>{item.val}</Text>
                <Text style={s.statLabel}>{item.label}</Text>
              </View>
            ))}
          </View>
        )}

        <Text style={s.sectionLabel}>{incidents.length} INCIDENTS · {lastUpdated}</Text>

        {incidents.length === 0 ? (
          <View style={s.center}>
            <Text style={{fontSize:40, marginBottom:12}}>🛡️</Text>
            <Text style={[s.logo, {color:'#00e676'}]}>ALL CLEAR</Text>
          </View>
        ) : incidents.map(inc => (
          <View key={inc.id} style={s.card}>
            <View style={s.cardTop}>
              <View style={{flex:1}}>
                <Text style={s.zone}><Text style={{color: confColor(inc.confidence)}}>{inc.zone === 'LEFT' ? '◀' : inc.zone === 'CENTER' ? '●' : '▶'} </Text>{inc.zone} ZONE</Text>
                <Text style={s.theater}>{inc.theater_name} · {inc.screen_number}</Text>
                {inc.seat_location && <Text style={s.seat}>📍 {inc.seat_location}</Text>}
              </View>
              <View style={{alignItems:'flex-end', gap:4}}>
                <Text style={[s.conf, {color: confColor(inc.confidence)}]}>{Math.round(inc.confidence*100)}%</Text>
                <Text style={s.time}>{timeAgo(inc.detected_at)}</Text>
                <View style={[s.badge, inc.alerted && s.badgeOn]}>
                  <Text style={[s.badgeText, inc.alerted && {color:'#00e676'}]}>{inc.alerted ? '✓ ALERTED' : 'PENDING'}</Text>
                </View>
              </View>
            </View>
            <View style={s.cardBot}>
              <Text style={s.film}>{inc.film_title}</Text>
              <View style={[s.type, inc.detection_type === 'PHONE' ? s.typePhone : s.typeCam]}>
                <Text style={s.typeText}>{inc.detection_type}</Text>
              </View>
            </View>
          </View>
        ))}

        <Text style={s.footer}>Auto-refreshes every 15s · Railway PostgreSQL</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:{flex:1,backgroundColor:'#06080b'},
  center:{flex:1,alignItems:'center',justifyContent:'center',padding:30,gap:12},
  loadText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)',letterSpacing:2},
  header:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingHorizontal:20,paddingVertical:14,borderBottomWidth:1,borderBottomColor:'rgba(255,255,255,0.08)'},
  logo:{fontFamily:'SpaceMono',fontSize:18,color:'#fff',letterSpacing:2},
  sub:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:2,marginTop:2},
  pill:{flexDirection:'row',alignItems:'center',gap:6,backgroundColor:'rgba(255,58,58,0.12)',borderWidth:1,borderColor:'rgba(255,58,58,0.3)',paddingHorizontal:10,paddingVertical:5,borderRadius:20},
  dot:{width:6,height:6,borderRadius:3,backgroundColor:'#ff3a3a'},
  pillText:{fontFamily:'SpaceMono',fontSize:9,color:'#ff3a3a',letterSpacing:1.5},
  statsRow:{flexDirection:'row',paddingHorizontal:20,paddingVertical:14,gap:10},
  statCard:{flex:1,backgroundColor:'#0e1216',borderWidth:1,borderColor:'rgba(255,255,255,0.08)',borderRadius:8,padding:12,alignItems:'center'},
  statVal:{fontFamily:'SpaceMono',fontSize:22,lineHeight:26},
  statLabel:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.4)',letterSpacing:1.5,marginTop:2},
  sectionLabel:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:1.5,paddingHorizontal:20,marginBottom:10},
  card:{marginHorizontal:20,marginBottom:10,backgroundColor:'#0e1216',borderWidth:1,borderColor:'rgba(255,255,255,0.08)',borderRadius:10,padding:14},
  cardTop:{flexDirection:'row',justifyContent:'space-between',marginBottom:10},
  zone:{fontFamily:'SpaceMono',fontSize:13,color:'#fff',letterSpacing:1,marginBottom:4},
  theater:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.5)',letterSpacing:0.5},
  seat:{fontFamily:'SpaceMono',fontSize:10,color:'#ffb700',marginTop:3},
  conf:{fontFamily:'SpaceMono',fontSize:18,lineHeight:22},
  time:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:1},
  badge:{paddingHorizontal:7,paddingVertical:3,borderRadius:4,borderWidth:1,borderColor:'rgba(255,255,255,0.1)',backgroundColor:'rgba(255,255,255,0.04)'},
  badgeOn:{borderColor:'rgba(0,230,118,0.3)',backgroundColor:'rgba(0,230,118,0.08)'},
  badgeText:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.35)',letterSpacing:1},
  cardBot:{flexDirection:'row',justifyContent:'space-between',alignItems:'center',borderTopWidth:1,borderTopColor:'rgba(255,255,255,0.06)',paddingTop:10},
  film:{fontFamily:'SpaceMono',fontSize:11,color:'rgba(255,255,255,0.6)',flex:1},
  type:{paddingHorizontal:8,paddingVertical:3,borderRadius:4},
  typePhone:{backgroundColor:'rgba(255,58,58,0.15)'},
  typeCam:{backgroundColor:'rgba(255,183,0,0.15)'},
  typeText:{fontFamily:'SpaceMono',fontSize:8,color:'#fff',letterSpacing:1},
  footer:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.2)',textAlign:'center',marginTop:16,letterSpacing:1,paddingBottom:20},
});
