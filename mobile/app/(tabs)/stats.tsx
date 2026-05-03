import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const API = 'https://cinerisk-api-production.up.railway.app';

export default function StatsScreen() {
  const [incidents, setIncidents] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [ir, sr] = await Promise.all([
        fetch(API + '/theater/incidents?limit=200'),
        fetch(API + '/theater/stats'),
      ]);
      setIncidents((await ir.json()).incidents || []);
      setStats(await sr.json());
    } catch(e) { console.error(e); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { fetchData(); }, []);

  const theaterMap = {};
  incidents.forEach(i => {
    const n = i.theater_name || 'Unknown';
    if (!theaterMap[n]) theaterMap[n] = [];
    theaterMap[n].push(i);
  });

  const filmMap = {};
  incidents.forEach(i => {
    const f = i.film_title || 'Unknown';
    if (!filmMap[f]) filmMap[f] = [];
    filmMap[f].push(i);
  });

  function compliance(n) { return Math.max(0, Math.round(100 - n * 2)); }
  function compColor(sc) { return sc >= 95 ? '#00e676' : sc >= 85 ? '#ffb700' : '#ff3a3a'; }

  if (loading) return (
    <SafeAreaView style={s.safe}>
      <View style={s.center}>
        <ActivityIndicator color="#ff3a3a" size="large" />
        <Text style={s.loadText}>LOADING STATS...</Text>
      </View>
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} tintColor="#ff3a3a" />}>

        <View style={s.header}>
          <View>
            <Text style={s.logo}>CINEOS</Text>
            <Text style={s.sub}>THEATER INTELLIGENCE</Text>
          </View>
          <View style={s.patentBadge}>
            <Text style={s.patentText}>US PROV. PAT. 64/049,190</Text>
          </View>
        </View>

        {stats && (
          <View>
            <Text style={s.sectionLabel}>NETWORK OVERVIEW</Text>
            <View style={s.bigRow}>
              <View style={[s.bigCard, {borderColor:'rgba(255,58,58,0.3)'}]}>
                <Text style={[s.bigVal, {color:'#ff3a3a'}]}>{stats.total_incidents}</Text>
                <Text style={s.bigLabel}>INCIDENTS</Text>
              </View>
              <View style={[s.bigCard, {borderColor:'rgba(255,183,0,0.3)'}]}>
                <Text style={[s.bigVal, {color:'#ffb700'}]}>{stats.theaters_active}</Text>
                <Text style={s.bigLabel}>THEATERS</Text>
              </View>
              <View style={[s.bigCard, {borderColor:'rgba(0,230,118,0.3)'}]}>
                <Text style={[s.bigVal, {color:'#00e676'}]}>{stats.compliance_score}</Text>
                <Text style={s.bigLabel}>COMPLIANCE</Text>
              </View>
            </View>
          </View>
        )}

        <Text style={s.sectionLabel}>THEATERS</Text>
        {Object.entries(theaterMap).sort((a,b) => b[1].length - a[1].length).map(([name, incs]) => {
          const score = compliance(incs.length);
          const zones = incs.reduce((acc, i) => { acc[i.zone] = (acc[i.zone]||0)+1; return acc; }, {});
          const avgConf = Math.round(incs.reduce((sum,i) => sum+i.confidence, 0) / incs.length * 100);
          return (
            <View key={name} style={s.theaterCard}>
              <View style={s.theaterTop}>
                <View style={{flex:1}}>
                  <Text style={s.theaterName}>{name}</Text>
                  <Text style={s.theaterMeta}>{incs.length} incidents · {avgConf}% avg conf</Text>
                </View>
                <View style={[s.compCircle, {borderColor: compColor(score)+'66'}]}>
                  <Text style={[s.compVal, {color: compColor(score)}]}>{score}</Text>
                  <Text style={s.compLabel}>COMP</Text>
                </View>
              </View>
              <View style={s.zoneRow}>
                {['LEFT','CENTER','RIGHT'].map(z => (
                  <View key={z} style={[s.zoneChip, (zones[z]||0) > 0 && s.zoneChipOn]}>
                    <Text style={[s.zoneChipText, (zones[z]||0) > 0 && {color:'#ff3a3a'}]}>{z[0]} {zones[z]||0}</Text>
                  </View>
                ))}
              </View>
            </View>
          );
        })}

        <Text style={s.sectionLabel}>FILMS</Text>
        {Object.entries(filmMap).map(([film, incs]) => {
          const avgConf = Math.round(incs.reduce((sum,i) => sum+i.confidence,0)/incs.length*100);
          return (
            <View key={film} style={s.filmCard}>
              <View style={{flex:1}}>
                <Text style={s.filmTitle}>{film}</Text>
                <Text style={s.filmMeta}>{incs.length} incidents · {[...new Set(incs.map(i=>i.theater_name))].length} theaters</Text>
              </View>
              <View style={{alignItems:'center'}}>
                <Text style={[s.filmConf, {color: avgConf >= 75 ? '#ff3a3a' : '#ffb700'}]}>{avgConf}%</Text>
                <Text style={s.filmConfLabel}>AVG</Text>
              </View>
            </View>
          );
        })}

        <View style={s.patentCard}>
          <Text style={s.patentCardTitle}>CINEOS CERTIFIED</Text>
          <Text style={s.patentCardSub}>US Provisional Patent 64/049,190</Text>
          <Text style={s.patentCardSub}>Filed April 24, 2026</Text>
        </View>

        <Text style={s.footer}>Pull to refresh · Railway PostgreSQL</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:{flex:1,backgroundColor:'#06080b'},
  center:{flex:1,alignItems:'center',justifyContent:'center',gap:12,padding:30},
  loadText:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)',letterSpacing:2},
  header:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',paddingHorizontal:20,paddingVertical:14,borderBottomWidth:1,borderBottomColor:'rgba(255,255,255,0.08)'},
  logo:{fontFamily:'SpaceMono',fontSize:18,color:'#fff',letterSpacing:2},
  sub:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:2,marginTop:2},
  patentBadge:{borderWidth:1,borderColor:'rgba(255,183,0,0.3)',borderRadius:6,padding:8,backgroundColor:'rgba(255,183,0,0.06)'},
  patentText:{fontFamily:'SpaceMono',fontSize:8,color:'#ffb700',letterSpacing:1,textAlign:'center'},
  sectionLabel:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.35)',letterSpacing:2,paddingHorizontal:20,marginTop:20,marginBottom:10},
  bigRow:{flexDirection:'row',paddingHorizontal:20,gap:10},
  bigCard:{flex:1,backgroundColor:'#0e1216',borderWidth:1,borderRadius:10,padding:14,alignItems:'center'},
  bigVal:{fontFamily:'SpaceMono',fontSize:28,lineHeight:32},
  bigLabel:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.35)',letterSpacing:1.5,marginTop:4,textAlign:'center'},
  theaterCard:{marginHorizontal:20,marginBottom:10,backgroundColor:'#0e1216',borderWidth:1,borderColor:'rgba(255,255,255,0.08)',borderRadius:10,padding:14},
  theaterTop:{flexDirection:'row',justifyContent:'space-between',marginBottom:12},
  theaterName:{fontFamily:'SpaceMono',fontSize:13,color:'#fff',letterSpacing:0.5,marginBottom:4},
  theaterMeta:{fontFamily:'SpaceMono',fontSize:10,color:'rgba(255,255,255,0.4)',letterSpacing:0.5},
  compCircle:{width:52,height:52,borderRadius:26,borderWidth:2,alignItems:'center',justifyContent:'center',backgroundColor:'#06080b'},
  compVal:{fontFamily:'SpaceMono',fontSize:16,lineHeight:18},
  compLabel:{fontFamily:'SpaceMono',fontSize:7,color:'rgba(255,255,255,0.4)',letterSpacing:1},
  zoneRow:{flexDirection:'row',gap:6},
  zoneChip:{paddingHorizontal:10,paddingVertical:5,borderRadius:5,borderWidth:1,borderColor:'rgba(255,255,255,0.08)',backgroundColor:'rgba(255,255,255,0.03)'},
  zoneChipOn:{borderColor:'rgba(255,58,58,0.3)',backgroundColor:'rgba(255,58,58,0.08)'},
  zoneChipText:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:1},
  filmCard:{marginHorizontal:20,marginBottom:8,backgroundColor:'#0e1216',borderWidth:1,borderColor:'rgba(255,255,255,0.08)',borderRadius:10,padding:14,flexDirection:'row',alignItems:'center',justifyContent:'space-between'},
  filmTitle:{fontFamily:'SpaceMono',fontSize:12,color:'#fff',letterSpacing:0.5,marginBottom:4},
  filmMeta:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:0.5},
  filmConf:{fontFamily:'SpaceMono',fontSize:22},
  filmConfLabel:{fontFamily:'SpaceMono',fontSize:8,color:'rgba(255,255,255,0.35)',letterSpacing:1},
  patentCard:{marginHorizontal:20,marginTop:10,padding:16,borderWidth:1,borderColor:'rgba(255,183,0,0.2)',backgroundColor:'rgba(255,183,0,0.04)',borderRadius:10,alignItems:'center'},
  patentCardTitle:{fontFamily:'SpaceMono',fontSize:13,color:'#ffb700',letterSpacing:2,marginBottom:6},
  patentCardSub:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.4)',letterSpacing:1,lineHeight:18},
  footer:{fontFamily:'SpaceMono',fontSize:9,color:'rgba(255,255,255,0.2)',textAlign:'center',marginTop:16,letterSpacing:1,paddingBottom:20},
});
