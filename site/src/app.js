(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var R = window.RR_RESULTS, LD = window.RR_JSONLD, NV = window.RR_NATIVE;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fmt = function (n) { return Number(n).toLocaleString('en-IN'); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  /* =====================================================================
     1. Read the Sport Schema JSON-LD (the ONLY input of the replay)
     ===================================================================== */
  var graph = LD['@graph'];
  var byId = {};
  graph.forEach(function (n) { byId[n['@id']] = n; });
  var arr = function (v) { return v == null ? [] : Array.isArray(v) ? v : [v]; };
  var val = function (v) { return (v && typeof v === 'object' && '@value' in v) ? v['@value'] : v; };
  var ref = function (v) { return v && typeof v === 'object' ? v['@id'] : v; };
  var local = function (id) { return String(id).split(/[\/:]/).pop(); };
  var types = function (n) { return arr(n['@type']); };
  var get = function (n, k) { return val(n[k]); };
  var node = function (v) { return byId[ref(v)]; };
  var KIND = { 'kab:Raid': 'raid', 'kab:Card': 'card', 'kab:Review': 'review', 'kab:Substitution': 'substitution', 'kab:PeriodStart': 'half_start', 'kab:PeriodEnd': 'half_end' };

  function modelFromJsonLd() {
    var evNode = graph.filter(function (n) { return types(n).indexOf('sport:Event') >= 0; })[0];
    var tpTeam = {}, teamIri = {};
    var teams = arr(evNode['sport:participation']).map(function (r) {
      var tp = node(r), t = node(tp['sport:participationBy']);
      var team = {
        id: get(t, 'kab:nativeId'), name: get(t, 'rdfs:label'), short: get(t, 'kab:shortName'),
        colour: get(t, 'kab:colour'), side: get(tp, 'sport:alignment'),
        score: parseInt(get(tp, 'sport:score'), 10), outcome: local(ref(tp['sport:eventOutcome']))
      };
      tpTeam[tp['@id']] = team.id; teamIri[t['@id']] = team.id;
      return team;
    }).sort(function (a) { return a.side === 'home' ? -1 : 1; });
    var players = {}, iriToPid = {};
    graph.forEach(function (ip) {
      if (types(ip).indexOf('sport:IndividualParticipation') < 0) return;
      var a = node(ip['sport:participationBy']);
      var p = {
        id: get(a, 'kab:nativeId'), name: get(a, 'rdfs:label'),
        jersey: parseInt(get(ip, 'sport:uniformNumberEvent'), 10),
        team: tpTeam[ref(ip['sport:teamParticipation'])],
        role: local(ref(ip['kab:playingRole'])),
        starter: local(ref(ip['sport:playerStatus'])) === 'starter',
        captain: get(ip, 'kab:captain')
      };
      players[p.id] = p; iriToPid[a['@id']] = p.id;
    });
    var actionId = {};
    graph.forEach(function (n) { if (types(n).indexOf('sport:Action') >= 0) actionId[n['@id']] = get(n, 'kab:nativeId'); });
    var P = function (v) { return iriToPid[ref(v)]; };
    var put = function (o, k, v) { if (v !== undefined && v !== null) o[k] = v; };
    var events = graph.filter(function (n) { return types(n).indexOf('sport:Action') >= 0; }).map(function (n) {
      var kind = types(n).map(function (t) { return KIND[t]; }).filter(Boolean)[0];
      var e = { type: kind };
      put(e, 'id', get(n, 'kab:nativeId'));
      put(e, 'seq', parseInt(get(n, 'sport:sequenceNumber'), 10));
      put(e, 'half', get(n, 'kab:half'));
      put(e, 'clock', get(n, 'kab:clockSeconds'));
      if (n['sport:participation']) e.team = tpTeam[ref(n['sport:participation'])];
      ['home_score:kab:homeScore', 'away_score:kab:awayScore', 'home_on_mat:kab:homeOnMat', 'away_on_mat:kab:awayOnMat'].forEach(function (s) {
        var i = s.indexOf(':'); put(e, s.slice(0, i), get(n, s.slice(i + 1)));
      });
      if (kind === 'raid') {
        e.raider = P(n['kab:raider']);
        put(e, 'duration', get(n, 'kab:raidDurationSeconds'));
        e.outcome = local(ref(n['kab:raidOutcome']));
        [['defenders_on_mat', 'kab:defendersOnMat'], ['touch_points', 'kab:touchPoints'], ['bonus', 'kab:bonusPoint'],
         ['tackle_points', 'kab:tacklePoints'], ['all_out_points', 'kab:allOutPoints'], ['raid_points', 'kab:raidPoints'],
         ['defence_points', 'kab:defencePoints'], ['do_or_die', 'kab:doOrDie'], ['super_raid', 'kab:superRaid'],
         ['super_tackle', 'kab:superTackle']].forEach(function (kv) { put(e, kv[0], get(n, kv[1])); });
        [['defenders_out', 'kab:defenderOut'], ['tackled_by', 'kab:tackledBy'], ['revived', 'kab:revived']].forEach(function (kv) {
          var l = arr(n[kv[1]]).map(P).sort(); if (l.length) e[kv[0]] = l;
        });
        if (n['kab:allOutTeam']) e.all_out_team = teamIri[ref(n['kab:allOutTeam'])];
      } else if (kind === 'card') {
        e.player = P(n['kab:player']);
        e.colour = local(ref(n['sport:infractionLevel']));
        put(e, 'reason', get(n, 'sport:infractionType'));
        put(e, 'suspension_seconds', get(n, 'kab:suspensionSeconds'));
      } else if (kind === 'review') {
        e.raid = actionId[ref(n['kab:reviewOf'])];
        e.result = local(ref(n['kab:reviewResult']));
        put(e, 'reviews_left', get(n, 'kab:reviewsRemaining'));
      } else if (kind === 'substitution') {
        e.player_out = P(n['kab:playerOut']); e.player_in = P(n['kab:playerIn']);
      }
      return e;
    }).sort(function (a, b) { return a.seq - b.seq; });
    var site = node(evNode['sport:location']);
    return { name: get(evNode, 'rdfs:label'), venue: site ? get(site, 'rdfs:label') : '', firstRaid: teamIri[ref(evNode['kab:firstRaidTeam'])],
             teams: teams, players: players, events: events };
  }

  var M = modelFromJsonLd();
  var HOME = M.teams[0], AWAY = M.teams[1];
  var TEAM = {}; TEAM[HOME.id] = HOME; TEAM[AWAY.id] = AWAY;
  var EV = M.events, N = EV.length;
  var pname = function (pid) { return M.players[pid] ? M.players[pid].name : pid; };
  var other = function (tid) { return tid === HOME.id ? AWAY.id : HOME.id; };

  /* ---- diff: JSON-LD-derived events vs the original JSON, field by field ---- */
  function deepEq(a, b) {
    if (Array.isArray(a) || Array.isArray(b)) {
      if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
      for (var i = 0; i < a.length; i++) if (!deepEq(a[i], b[i])) return false;
      return true;
    }
    return a === b;   // strict: 2 !== "2", false !== 0
  }
  var DIFF = (function () {
    var diffs = 0, fields = 0;
    var n = Math.max(NV.events.length, EV.length);
    for (var i = 0; i < n; i++) {
      var a = NV.events[i] || {}, b = EV[i] || {};
      var keys = {}; Object.keys(a).concat(Object.keys(b)).forEach(function (k) { keys[k] = 1; });
      Object.keys(keys).forEach(function (k) { fields++; if (!deepEq(a[k], b[k])) diffs++; });
    }
    NV.teams.forEach(function (t, i) {
      var b = M.teams[i];
      ['id', 'name', 'short', 'colour', 'side'].forEach(function (k) { fields++; if (t[k] !== b[k]) diffs++; });
      t.players.forEach(function (p) {
        var q = M.players[p.id] || {};
        ['name', 'jersey', 'role', 'starter', 'captain'].forEach(function (k) { fields++; if (p[k] !== q[k]) diffs++; });
      });
    });
    return { diffs: diffs, fields: fields };
  })();

  /* ---- running scores: one from the native JSON, one from Sport Schema ---- */
  function runningScores(events, homeId) {
    var h = 0, a = 0, out = [[0, 0]];
    events.forEach(function (e) {
      if (e.type === 'raid') {
        var hp = e.team === homeId ? e.raid_points : e.defence_points;
        var ap = e.team === homeId ? e.defence_points : e.raid_points;
        h += hp; a += ap;
      }
      out.push([h, a]);
    });
    return out;
  }
  var SC_NATIVE = runningScores(NV.events, NV.teams[0].id);
  var SC_LD = runningScores(EV, HOME.id);

  /* =====================================================================
     2. Page furniture: nav, reveal, tabs, hero stats
     ===================================================================== */
  var nav = $('#nav');
  var onScroll = function () { nav.classList.toggle('scrolled', window.scrollY > 40); };
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  if ('IntersectionObserver' in window && !reduceMotion) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { threshold: 0.12 });
    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('in'); });
  }

  document.querySelectorAll('.tab-bar button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.tab-bar button').forEach(function (x) { x.setAttribute('aria-selected', x === b); });
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('active', p.id === b.dataset.tab); });
    });
  });

  var MS = R.matches;
  var sum = function (k) { return MS.reduce(function (s, m) { return s + m[k]; }, 0); };
  var totalDiff = sum('diff_turtle') + sum('diff_jsonld');
  var validFiles = MS.reduce(function (s, m) { return s + (m.valid_turtle ? 1 : 0) + (m.valid_jsonld ? 1 : 0); }, 0);

  $('#stats').innerHTML = [
    [MS.length, 'matches simulated'], [fmt(sum('events')), 'raid-by-raid events'], [fmt(sum('triples')), 'RDF triples'],
    [totalDiff, 'differences after round trip'], [validFiles + ' / ' + MS.length * 2, 'files pass SHACL']
  ].map(function (s) { return '<div class="stat"><b>' + s[0] + '</b><span>' + s[1] + '</span></div>'; }).join('');

  /* hero score card counts up to the final score read from JSON-LD */
  (function () {
    var hEl = $('#heroHome'), aEl = $('#heroAway'), t0 = null, D = 1600;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min(1, (ts - t0) / D), e = 1 - Math.pow(1 - p, 3);
      hEl.textContent = Math.round(HOME.score * e); aEl.textContent = Math.round(AWAY.score * e);
      if (p < 1) requestAnimationFrame(step);
    }
    if (reduceMotion) { hEl.textContent = HOME.score; aEl.textContent = AWAY.score; } else setTimeout(function () { requestAnimationFrame(step); }, 500);
  })();

  /* =====================================================================
     3. The replay
     ===================================================================== */
  var SVGNS = 'http://www.w3.org/2000/svg';
  var U = 60, MID = 486, TOP = 60;
  var sideOf = function (tid) { return tid === HOME.id ? 'home' : 'away'; };
  var hx = function (side, d) { return side === 'home' ? MID - d * U : MID + d * U; };
  var my = function (m) { return TOP + m * U; };
  var playersLayer = $('#players'), fx = $('#fx'), fxTop = $('#fxTop');

  // HUD + boards
  [['#hudHomeName', HOME.name], ['#hudAwayName', AWAY.name], ['#bjHomeName', HOME.name], ['#bjAwayName', AWAY.name], ['#brHomeName', HOME.name], ['#brAwayName', AWAY.name],
   ['#fjHomeName', HOME.short], ['#fjAwayName', AWAY.short], ['#frHomeName', HOME.short], ['#frAwayName', AWAY.short]]
    .forEach(function (x) { $(x[0]).textContent = x[1]; });
  ['#hudHomeSw', '#bjHomeSw', '#brHomeSw', '#fjHomeSw', '#frHomeSw'].forEach(function (s) { $(s).style.background = HOME.colour; });
  ['#hudAwaySw', '#bjAwaySw', '#brAwaySw', '#fjAwaySw', '#frAwaySw'].forEach(function (s) { $(s).style.background = AWAY.colour; });
  $('#diffN').textContent = DIFF.diffs;
  $('#diffTick').textContent = DIFF.diffs === 0 ? '✓' : '✕';
  $('#diffBadge').classList.toggle('bad', DIFF.diffs !== 0);
  $('#fsDiff').textContent = 'diff = ' + DIFF.diffs + ' ' + (DIFF.diffs === 0 ? '✓' : '✕');
  $('#fsDiff').classList.toggle('bad', DIFF.diffs !== 0);
  $('#diffSmall').textContent = fmt(DIFF.fields) + ' fields compared across ' + N + ' events and ' + Object.keys(M.players).length + ' players';

  // sprites
  var SPR = {};
  Object.keys(M.players).forEach(function (pid) {
    var p = M.players[pid];
    var g = document.createElementNS(SVGNS, 'g'); g.setAttribute('class', 'pl');
    var ring = document.createElementNS(SVGNS, 'circle'); ring.setAttribute('r', 30); ring.setAttribute('class', 'ring');
    var c = document.createElementNS(SVGNS, 'circle'); c.setAttribute('r', 22); c.setAttribute('class', 'body'); c.setAttribute('fill', TEAM[p.team].colour);
    var t = document.createElementNS(SVGNS, 'text'); t.textContent = p.jersey;
    var title = document.createElementNS(SVGNS, 'title'); title.textContent = p.name + ' (' + p.team + ' #' + p.jersey + ', ' + p.role + ')';
    g.appendChild(ring); g.appendChild(c); g.appendChild(t); g.appendChild(title);
    playersLayer.appendChild(g);
    SPR[pid] = { g: g, x: hx(sideOf(p.team), 3), y: my(5), tx: 0, ty: 0, o: 1, to: 1, free: false };
  });

  // match state
  var S;
  function initialState() {
    var s = { mat: {}, out: {}, susp: {}, red: {}, bench: {} };
    M.teams.forEach(function (t) {
      var ps = Object.keys(M.players).map(function (k) { return M.players[k]; }).filter(function (p) { return p.team === t.id; })
        .sort(function (a, b) { return a.jersey - b.jersey; });
      s.mat[t.id] = ps.filter(function (p) { return p.starter; }).map(function (p) { return p.id; });
      s.bench[t.id] = ps.filter(function (p) { return !p.starter; }).map(function (p) { return p.id; });
      s.out[t.id] = []; s.susp[t.id] = [];
    });
    return s;
  }
  var absT = function (e) { return (e.half - 1) * 1200 + e.clock; };
  var removeFrom = function (list, x) { var i = list.indexOf(x); if (i >= 0) list.splice(i, 1); return i >= 0; };

  function release(e) {   // yellow-card suspensions end (mirrors the simulator)
    M.teams.forEach(function (t) {
      S.susp[t.id] = S.susp[t.id].filter(function (s) {
        if (absT(e) >= s.until) { (S.mat[t.id].length < 7 ? S.mat[t.id] : S.out[t.id]).push(s.p); return false; }
        return true;
      });
    });
  }
  function applyEvent(e) {
    if (e.type === 'raid') {
      var att = e.team, dfn = other(att);
      (e.defenders_out || []).forEach(function (p) { removeFrom(S.mat[dfn], p); S.out[dfn].push(p); });
      if (e.outcome === 'tackled' || e.outcome === 'do-or-die-out' || e.outcome === 'self-out') {
        removeFrom(S.mat[att], e.raider); S.out[att].push(e.raider);
      }
      (e.revived || []).forEach(function (p) { var t = M.players[p].team; removeFrom(S.out[t], p); S.mat[t].push(p); });
    } else if (e.type === 'card') {
      var tm = M.players[e.player].team;
      if (e.colour === 'yellow') { removeFrom(S.mat[tm], e.player); S.susp[tm].push({ p: e.player, until: absT(e) + (e.suspension_seconds || 120) }); }
      if (e.colour === 'red') { removeFrom(S.mat[tm], e.player); S.red[e.player] = 1; }
    } else if (e.type === 'substitution') {
      var m = S.mat[e.team], i = m.indexOf(e.player_out);
      if (i >= 0) m[i] = e.player_in;
      var b = S.bench[e.team], j = b.indexOf(e.player_in); if (j >= 0) b[j] = e.player_out;
    }
    if (e.home_on_mat !== undefined && (S.mat[HOME.id].length !== e.home_on_mat || S.mat[AWAY.id].length !== e.away_on_mat)) {
      console.warn('on-mat mismatch at event', e.seq, S.mat[HOME.id].length, e.home_on_mat, S.mat[AWAY.id].length, e.away_on_mat);
    }
  }
  function preEvent(e) { if (e.type === 'raid' || e.type === 'card' || e.type === 'substitution') release(e); }

  // formation targets
  function slot(side, i, n) {
    var t = n <= 1 ? 0.5 : i / (n - 1);
    var d = 4.35 + 1.35 * (1 - Math.pow(2 * t - 1, 2));
    return { x: hx(side, d), y: my(0.9 + t * 8.2) };
  }
  function layout(exceptPid) {
    M.teams.forEach(function (t) {
      var side = sideOf(t.id);
      var mat = S.mat[t.id].filter(function (p) { return p !== exceptPid; });
      mat.forEach(function (p, i) { var s = slot(side, i, mat.length); var sp = SPR[p]; sp.tx = s.x; sp.ty = s.y; sp.by = s.y; sp.to = 1; });
      var colX = side === 'home' ? 48 : 924;
      S.out[t.id].forEach(function (p, i) { var sp = SPR[p]; sp.tx = colX; sp.ty = 128 + i * 44; sp.to = 1; });
      S.susp[t.id].forEach(function (s, i) { var sp = SPR[s.p]; sp.tx = colX; sp.ty = 640 - i * 44; sp.to = 1; });
      S.bench[t.id].forEach(function (p) { var sp = SPR[p]; sp.tx = colX; sp.ty = 700; sp.to = 0; });
    });
    Object.keys(S.red).forEach(function (p) { SPR[p].to = 0; });
    Object.keys(SPR).forEach(function (p) {
      var t = M.players[p].team;
      var isOut = S.out[t].indexOf(p) >= 0;
      var isSusp = S.susp[t].some(function (s) { return s.p === p; });
      SPR[p].g.classList.toggle('out', isOut || isSusp);
      SPR[p].g.classList.toggle('susp', isSusp);
    });
  }
  function snap() { Object.keys(SPR).forEach(function (p) { var s = SPR[p]; s.x = s.tx; s.y = s.ty; s.o = s.to; }); }

  // effects
  function ring(x, y, colour, r0, r1, ms) {
    var c = document.createElementNS(SVGNS, 'circle');
    c.setAttribute('cx', x); c.setAttribute('cy', y); c.setAttribute('fill', 'none'); c.setAttribute('stroke', colour); c.setAttribute('stroke-width', 5);
    fxTop.appendChild(c);
    var t0 = performance.now();
    (function f(ts) {
      var p = Math.min(1, (ts - t0) / ms);
      c.setAttribute('r', r0 + (r1 - r0) * p); c.setAttribute('opacity', 1 - p);
      if (p < 1) requestAnimationFrame(f); else c.remove();
    })(t0);
  }
  function floatText(x, y, txt, colour) {
    var t = document.createElementNS(SVGNS, 'text');
    t.setAttribute('x', x); t.setAttribute('y', y); t.setAttribute('text-anchor', 'middle');
    t.setAttribute('style', 'font:900 26px ' + getComputedStyle(document.body).fontFamily + ';fill:' + colour + ';paint-order:stroke;stroke:#0c1035;stroke-width:5px');
    t.textContent = txt; fxTop.appendChild(t);
    var t0 = performance.now();
    (function f(ts) {
      var p = Math.min(1, (ts - t0) / 1100);
      t.setAttribute('y', y - 50 * p); t.setAttribute('opacity', p < 0.7 ? 1 : 1 - (p - 0.7) / 0.3);
      if (p < 1) requestAnimationFrame(f); else t.remove();
    })(t0);
  }
  function flashBonus(side) {
    var x = hx(side, 4.75);
    var l = document.createElementNS(SVGNS, 'line');
    l.setAttribute('x1', x); l.setAttribute('x2', x); l.setAttribute('y1', 60); l.setAttribute('y2', 660);
    l.setAttribute('stroke', '#FFD166'); l.setAttribute('stroke-width', 10); l.setAttribute('filter', 'url(#glow)');
    fx.appendChild(l);
    setTimeout(function () { l.remove(); }, 700);
  }
  var tagsEl = $('#tags'), overlayEl = $('#overlay');
  function tag(text, cls, ms) {
    var el = document.createElement('div'); el.className = 'tag ' + cls; el.textContent = text;
    tagsEl.appendChild(el);
    var life = Math.max(700, (ms || 1800) / Math.sqrt(speed));
    setTimeout(function () { el.classList.add('out'); setTimeout(function () { el.remove(); }, 350); }, life);
  }
  function clearTags() { tagsEl.innerHTML = ''; }
  function overlay(title, sub, ms) {
    overlayEl.innerHTML = '<div class="big"><b>' + esc(title) + '</b><span>' + esc(sub) + '</span></div>';
    if (ms) setTimeout(function () { overlayEl.innerHTML = ''; }, Math.max(900, ms / speed));
  }

  // commentary
  function teamName(tid) { return TEAM[tid].name; }
  function commentary(e) {
    var sc = function () { return HOME.short + ' ' + e.home_score + ' – ' + e.away_score + ' ' + AWAY.short; };
    switch (e.type) {
      case 'half_start':
        return e.half === 1 ? M.name + ' is under way at ' + M.venue.replace(/ \(fictional\)/, '') + '. ' + teamName(M.firstRaid) + ' raid first.'
          : 'Second half begins: ' + sc() + '.';
      case 'half_end':
        if (e.half === 1) return 'Half-time: ' + sc() + '.';
        var w = HOME.outcome === 'win' ? HOME : AWAY.outcome === 'win' ? AWAY : null;
        return 'Full-time: ' + sc() + (w ? '. ' + w.name + ' are champions!' : '. A tie!');
      case 'card':
        return (e.colour.charAt(0).toUpperCase() + e.colour.slice(1)) + ' card for ' + pname(e.player) + ' (' + TEAM[e.team].short + ') — ' + (e.reason || '').toLowerCase() +
          (e.suspension_seconds ? '. Off for ' + e.suspension_seconds / 60 + ' minutes.' : e.colour === 'red' ? '. Out for the rest of the match.' : '.');
      case 'review':
        return teamName(e.team) + ' review raid #' + parseInt(e.raid.split('-E')[1], 10) + ' — ' + (e.result === 'successful' ? 'call overturned, review retained' : 'call upheld') + ' (' + e.reviews_left + ' left).';
      case 'substitution':
        return TEAM[e.team].short + ' substitution: ' + pname(e.player_in) + ' comes on for ' + pname(e.player_out) + '.';
    }
    var who = pname(e.raider) + ' (' + TEAM[e.team].short + ')';
    var s;
    if (e.outcome === 'successful') {
      var bits = [];
      if (e.touch_points) bits.push(e.touch_points + ' touch point' + (e.touch_points > 1 ? 's' : ''));
      if (e.bonus) bits.push('the bonus');
      s = who + ' scores ' + bits.join(' + ') + (e.super_raid ? ' — SUPER RAID!' : '.');
    } else if (e.outcome === 'tackled') {
      s = who + ' is tackled by ' + (e.tackled_by || []).map(pname).join(' & ') + (e.super_tackle ? ' — SUPER TACKLE with only ' + e.defenders_on_mat + ' on the mat!' : '.') + (e.bonus ? ' (bonus still counts)' : '');
    } else if (e.outcome === 'empty') {
      s = who + ' returns empty-handed. Empty raid.';
    } else if (e.outcome === 'do-or-die-out') {
      s = who + ' fails the do-or-die raid and is declared out.';
    } else {
      s = who + ' steps into the lobby without a struggle — self out.';
    }
    if (e.all_out_team) s += ' ALL OUT! ' + teamName(e.all_out_team) + ' concede 2 extra points.';
    return s;
  }

  // HUD
  var hudH = $('#hudHomeScore'), hudA = $('#hudAwayScore');
  var bj = [$('#bjHome'), $('#bjAway')], br = [$('#brHome'), $('#brAway')];
  var fj = [$('#fjHome'), $('#fjAway')], fr = [$('#frHome'), $('#frAway')];   // compact full-screen panel
  function setBoards(k) {   // k = number of events applied
    var a = SC_NATIVE[Math.min(k, SC_NATIVE.length - 1)], b = SC_LD[Math.min(k, SC_LD.length - 1)];
    [[bj[0], a[0]], [bj[1], a[1]], [br[0], b[0]], [br[1], b[1]], [hudH, b[0]], [hudA, b[1]],
     [fj[0], a[0]], [fj[1], a[1]], [fr[0], b[0]], [fr[1], b[1]]].forEach(function (x) {
      if (x[0].textContent !== String(x[1])) {
        x[0].textContent = x[1];
        if (x[0].tagName === 'B') { x[0].classList.add('bump'); setTimeout(function () { x[0].classList.remove('bump'); }, 500); }
      }
    });
  }
  var clockEl = $('#hudClock'), barEl = $('#raidBar'), raidInfo = $('#hudRaid'), comEl = $('#commentary');
  function setClock(half, secs) {
    secs = Math.max(0, Math.min(1200, Math.floor(secs)));
    clockEl.textContent = 'H' + half + ' ' + String(Math.floor(secs / 60)).padStart(2, '0') + ':' + String(secs % 60).padStart(2, '0');
  }
  function say(e) { comEl.innerHTML = '<span class="cm-seq">#' + e.seq + '</span><span>' + esc(commentary(e)) + '</span>'; }

  // timeline ticks
  var scrub = $('#scrub'); scrub.max = N;
  var tickColour = function (e) {
    if (e.type === 'raid') return { successful: '#ff8a00', tackled: '#00c2d1', empty: 'rgba(255,255,255,.35)', 'do-or-die-out': '#ff3b5c', 'self-out': '#ff3b5c' }[e.outcome];
    return { card: '#ffd23f', review: '#ffffff', substitution: '#6d7cff', half_start: '#ffffff', half_end: '#ffffff' }[e.type];
  };
  $('#ticks').innerHTML = EV.map(function (e, i) {
    var tall = e.type === 'half_end' || e.type === 'half_start' || e.super_raid || e.super_tackle || e.all_out_team;
    return '<i style="left:' + ((i + 0.5) / N * 100) + '%;background:' + tickColour(e) + (tall ? ';height:14px;top:-2px' : '') + '"></i>';
  }).join('');

  /* ---- playback engine ---- */
  var idx = 0, cur = null, playing = false, speed = 1, lastTs = null, raidPlan = null;
  var evCount = $('#evCount');

  function eventMs(e) {
    if (e.type === 'raid') return 2700 + 260 * (e.touch_points || 0) + (e.bonus ? 250 : 0) + (e.outcome === 'tackled' ? 400 : 0);
    if (e.type === 'half_end') return 2600;
    if (e.type === 'review' || e.type === 'card') return 2100;
    return 1300;
  }

  function planRaid(e) {
    var att = sideOf(e.team), def = att === 'home' ? 'away' : 'home';
    var sp = SPR[e.raider];
    var jitter = ((e.seq * 37) % 100) / 100;                 // deterministic variety
    var yLane = 2.6 + jitter * 4.8;
    var pts = [{ x: sp.x, y: sp.y }, { x: hx(att, 0.5), y: my(yLane) }, { x: hx(def, 1.2), y: my(yLane) }];
    var marks = [];
    if (e.bonus) { var by = jitter > 0.5 ? 8.6 : 1.4; pts.push({ x: hx(def, 4.95), y: my(by), mark: 'bonus' }); }
    (e.defenders_out || []).forEach(function (p) {
      var d = SPR[p];
      var dx = att === 'home' ? -38 : 38;
      pts.push({ x: d.tx + dx, y: d.ty, mark: 'touch', pid: p });
    });
    if (e.outcome === 'empty' || e.outcome === 'do-or-die-out' || (e.outcome === 'tackled' && !e.bonus) || (e.outcome === 'successful' && !e.bonus && !(e.defenders_out || []).length)) {
      pts.push({ x: hx(def, 4.0), y: my(Math.max(1.5, Math.min(8.5, yLane + (jitter - 0.5) * 2))), mark: 'baulk' });
    }
    if (e.outcome === 'self-out') pts.push({ x: hx(def, 2.6 + jitter * 2), y: my(jitter > 0.5 ? 10.55 : -0.55), mark: 'lobby' });
    var attackEnd = e.outcome === 'tackled' ? 0.6 : 0.62;
    var back = [];
    if (e.outcome === 'successful' || e.outcome === 'empty' || e.outcome === 'do-or-die-out') {
      var last = pts[pts.length - 1];
      back = [last, { x: hx(def, 1.0), y: (last.y + my(5)) / 2 }, { x: hx(att, 0.9), y: my(5) }];
    }
    function lens(list) { var L = [0]; for (var i = 1; i < list.length; i++) L.push(L[i - 1] + Math.hypot(list[i].x - list[i - 1].x, list[i].y - list[i - 1].y)); return L; }
    var LA = lens(pts), LB = back.length ? lens(back) : null;
    pts.forEach(function (p, i) { if (p.mark) marks.push({ at: 0.06 + (attackEnd - 0.06) * (LA[i] / LA[LA.length - 1]), p: p, done: false }); });
    return { e: e, att: att, def: def, pts: pts, LA: LA, back: back, LB: LB, attackEnd: attackEnd, marks: marks, tackleShown: false };
  }
  function along(list, L, f) {
    var total = L[L.length - 1], d = f * total;
    for (var i = 1; i < list.length; i++) {
      if (d <= L[i] || i === list.length - 1) {
        var seg = L[i] - L[i - 1] || 1, u = Math.max(0, Math.min(1, (d - L[i - 1]) / seg));
        return { x: list[i - 1].x + (list[i].x - list[i - 1].x) * u, y: list[i - 1].y + (list[i].y - list[i - 1].y) * u };
      }
    }
    return list[list.length - 1];
  }
  var ease = function (t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; };

  function startEvent() {
    var e = EV[idx];
    preEvent(e);
    cur = { e: e, t: 0, ms: eventMs(e) };
    say(e);
    raidInfo.textContent = ' ';
    if (e.type === 'raid') {
      layout(e.raider);
      raidPlan = planRaid(e);
      var sp = SPR[e.raider]; sp.free = true; sp.g.classList.add('raider');
      playersLayer.appendChild(sp.g);       // raider on top
      raidInfo.textContent = 'Raid #' + e.seq + ' · ' + TEAM[e.team].short + ' · ' + e.defenders_on_mat + ' defender' + (e.defenders_on_mat === 1 ? '' : 's');
      if (e.do_or_die) tag('DO-OR-DIE', 't-dod', 2400);
    } else {
      raidPlan = null;
      if (e.type === 'card') tag((e.colour === 'yellow' ? '▮ YELLOW CARD' : e.colour === 'red' ? '▮ RED CARD' : '▮ GREEN CARD'), 't-' + e.colour, 2200);
      if (e.type === 'review') tag('REVIEW · ' + (e.result === 'successful' ? 'OVERTURNED' : 'UPHELD'), 't-review', 2200);
      if (e.type === 'substitution') tag('SUBSTITUTION ⇄ ' + TEAM[e.team].short, 't-sub', 1600);
      if (e.type === 'half_start') { overlayEl.innerHTML = ''; tag(e.half === 1 ? 'KICK-OFF' : 'SECOND HALF', 't-half', 1400); }
      if (e.type === 'half_end') overlay(e.half === 1 ? 'Half-time' : 'Full-time', HOME.short + ' ' + e.home_score + ' – ' + e.away_score + ' ' + AWAY.short, e.half === 1 ? 2600 : 0);
      if (e.type === 'card') { var s = SPR[e.player]; ring(s.x, s.y, e.colour === 'red' ? '#e5484d' : e.colour === 'yellow' ? '#ffd23f' : '#18b26b', 20, 60, 900); }
      setClock(e.half, e.clock);
    }
  }

  function updateEvent(dt) {
    var e = cur.e;
    cur.t += dt * speed;
    var p = Math.min(1, cur.t / cur.ms);
    if (raidPlan) {
      var rp = raidPlan, sp = SPR[e.raider];
      var pos;
      if (p <= rp.attackEnd) {
        var f = ease(Math.min(1, Math.max(0, (p - 0.06) / (rp.attackEnd - 0.06))));
        pos = p < 0.06 ? rp.pts[0] : along(rp.pts, rp.LA, f);
      } else if (rp.back.length) {
        var g = ease(Math.min(1, (p - rp.attackEnd) / (0.95 - rp.attackEnd)));
        pos = along(rp.back, rp.LB, g);
      } else {
        pos = rp.pts[rp.pts.length - 1];
      }
      sp.x = pos.x; sp.y = pos.y;
      rp.marks.forEach(function (m) {
        if (m.done || p < m.at) return;
        m.done = true;
        if (m.p.mark === 'touch') { var d = SPR[m.p.pid]; ring(d.x, d.y, '#ff3b5c', 18, 56, 650); floatText(d.x, d.y - 30, '+1', '#ffd166'); d.g.classList.add('out'); }
        if (m.p.mark === 'bonus') { flashBonus(rp.def); tag('BONUS', 't-bonus', 1600); floatText(pos.x, pos.y - 34, '+1', '#ffb347'); }
        if (m.p.mark === 'lobby') { ring(pos.x, pos.y, '#ff3b5c', 18, 60, 700); tag('SELF OUT', 't-dod', 1600); }
      });
      // defenders react: drift towards the raider's lane
      S.mat[e.team === HOME.id ? AWAY.id : HOME.id].forEach(function (pid) {
        var d = SPR[pid]; if (!d || d.by === undefined) return;
        if (e.outcome === 'tackled' && p > rp.attackEnd && (e.tackled_by || []).indexOf(pid) >= 0) return;
        d.ty = d.by + (pos.y - d.by) * 0.16;
      });
      if (e.outcome === 'tackled' && p > rp.attackEnd) {
        (e.tackled_by || []).forEach(function (pid, k, all) {
          var a = (k / Math.max(1, all.length)) * Math.PI * 2 + 0.6;
          var d = SPR[pid]; d.tx = pos.x + Math.cos(a) * 34; d.ty = pos.y + Math.sin(a) * 34;
        });
        if (!rp.tackleShown && p > rp.attackEnd + 0.08) {
          rp.tackleShown = true;
          ring(pos.x, pos.y, '#00c2d1', 20, 70, 800);
          tag(e.super_tackle ? 'SUPER TACKLE' : 'TACKLED', e.super_tackle ? 't-st' : 't-st', 2000);
          floatText(pos.x, pos.y - 36, '+' + e.tackle_points, '#7fe9f5');
        }
      }
      if (e.outcome === 'do-or-die-out' && p > 0.93 && !rp.dodShown) { rp.dodShown = true; ring(pos.x, pos.y, '#ff3b5c', 18, 60, 700); tag('OUT · DO-OR-DIE FAILED', 't-dod', 1600); }
      var spot = $('#spotlight'); spot.setAttribute('cx', pos.x); spot.setAttribute('cy', pos.y); spot.setAttribute('opacity', 1);
      setClock(e.half, e.clock + Math.min(1, p / 0.95) * e.duration);
      barEl.style.width = (Math.min(1, p / 0.95) * e.duration / 30 * 100) + '%';
    }
    if (p >= 1) finishEvent();
  }

  function finishEvent() {
    var e = cur.e;
    applyEvent(e);
    if (e.type === 'raid') {
      var sp = SPR[e.raider]; sp.free = false; sp.g.classList.remove('raider');
      $('#spotlight').setAttribute('opacity', 0);
      if (e.super_raid) tag('SUPER RAID', 't-sr', 2200);
      if (e.all_out_team) {
        tag('ALL OUT +2', 't-ao', 2400);
        var side = sideOf(e.all_out_team);
        ring(hx(side, 3.25), my(5), '#e0218a', 60, 260, 1100);
      }
      if (e.raid_points > 0 && e.outcome === 'successful') ring(sp.x, sp.y, '#ff8a00', 20, 46, 500);
    }
    idx++;
    cur = null; raidPlan = null;
    layout(null);
    setBoards(idx);
    syncScrub();
    if (idx >= N) { setPlaying(false); }
  }

  function syncScrub() { scrub.value = idx; evCount.textContent = idx + ' / ' + N; }

  function seek(k) {
    k = Math.max(0, Math.min(N, k));
    S = initialState();
    for (var i = 0; i < k; i++) { preEvent(EV[i]); applyEvent(EV[i]); }
    idx = k; cur = null; raidPlan = null;
    Object.keys(SPR).forEach(function (p) { SPR[p].free = false; SPR[p].g.classList.remove('raider'); });
    clearTags(); overlayEl.innerHTML = ''; barEl.style.width = '0';
    $('#spotlight').setAttribute('opacity', 0);
    layout(null); snap(); render(0);
    setBoards(idx); syncScrub();
    if (k > 0) { var e = EV[k - 1]; say(e); setClock(e.half, e.type === 'raid' ? e.clock + e.duration : e.clock); }
    else { comEl.textContent = 'Press play to start the replay.'; setClock(1, 0); }
    if (k >= N) overlay('Full-time', HOME.short + ' ' + HOME.score + ' – ' + AWAY.score + ' ' + AWAY.short, 0);
  }

  function render(dt) {
    var k = 1 - Math.exp(-dt * 9);
    Object.keys(SPR).forEach(function (p) {
      var s = SPR[p];
      if (!s.free) { s.x += (s.tx - s.x) * (dt ? k : 1); s.y += (s.ty - s.y) * (dt ? k : 1); }
      s.o += (s.to - s.o) * (dt ? k : 1);
      s.g.setAttribute('transform', 'translate(' + s.x.toFixed(1) + ',' + s.y.toFixed(1) + ')');
      s.g.style.opacity = s.o.toFixed(2);
    });
  }

  function frame(ts) {
    var dt = lastTs === null ? 0 : Math.min(0.05, (ts - lastTs) / 1000);
    lastTs = ts;
    if (playing) {
      if (!cur && idx < N) startEvent();
      if (cur) updateEvent(dt * 1000);
    }
    render(dt);
    requestAnimationFrame(frame);
  }

  var btnPlay = $('#btnPlay'), playIcon = $('#playIcon');
  function setPlaying(v) {
    playing = v;
    if (v && idx >= N) seek(0);
    playIcon.setAttribute('d', v ? 'M6 4h4v16H6zM14 4h4v16h-4z' : 'M7 4.5v15l12-7.5z');
    btnPlay.setAttribute('aria-label', v ? 'Pause' : 'Play');
  }
  btnPlay.addEventListener('click', function () { setPlaying(!playing); });
  $('#btnNext').addEventListener('click', function () { seek(idx + (cur ? 1 : 1)); });
  $('#btnPrev').addEventListener('click', function () { seek(idx - 1); });
  scrub.addEventListener('input', function () { seek(parseInt(scrub.value, 10)); });
  document.querySelectorAll('.speed button').forEach(function (b) {
    b.addEventListener('click', function () {
      speed = parseFloat(b.dataset.speed);
      document.querySelectorAll('.speed button').forEach(function (x) { x.classList.toggle('on', x === b); });
    });
  });

  /* ---- full screen: mat + HUD + commentary + controls, with a compact score panel ---- */
  var matWrap = $('#matWrap'), btnFs = $('#btnFs'), fsLabel = $('#fsLabel');
  var fsElement = function () { return document.fullscreenElement || document.webkitFullscreenElement || null; };
  var pseudoFs = false;   // fallback where the Fullscreen API is missing (e.g. iPhone Safari)
  function syncFs() {
    var on = fsElement() === matWrap || pseudoFs;
    matWrap.classList.toggle('fs', on);
    matWrap.classList.toggle('fs-pseudo', pseudoFs);
    document.body.classList.toggle('rr-fs', on);
    fsLabel.textContent = on ? 'Exit full screen' : 'Full screen';
    btnFs.setAttribute('aria-label', on ? 'Exit full screen (Esc)' : 'Full screen (F)');
    btnFs.setAttribute('title', on ? 'Exit full screen (Esc)' : 'Full screen (F)');
    btnFs.setAttribute('aria-pressed', on);
  }
  function setPseudo(v) { pseudoFs = v; syncFs(); }
  function enterFs() {
    var req = matWrap.requestFullscreen || matWrap.webkitRequestFullscreen;
    if (!req) { setPseudo(true); return; }
    try {
      var r = req.call(matWrap);
      if (r && r.catch) r.catch(function () { setPseudo(true); });
    } catch (err) { setPseudo(true); }
  }
  function exitFs() {
    if (pseudoFs) { setPseudo(false); return; }
    var ex = document.exitFullscreen || document.webkitExitFullscreen;
    if (fsElement() && ex) ex.call(document);
  }
  function toggleFs() { if (fsElement() === matWrap || pseudoFs) exitFs(); else enterFs(); }
  btnFs.addEventListener('click', toggleFs);
  document.addEventListener('fullscreenchange', syncFs);
  document.addEventListener('webkitfullscreenchange', syncFs);
  document.addEventListener('keydown', function (ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    var t = ev.target;
    if (t && (t.isContentEditable || /^(TEXTAREA|SELECT)$/.test(t.tagName) || (t.tagName === 'INPUT' && t.type !== 'range'))) return;
    if (ev.key === 'f' || ev.key === 'F') { ev.preventDefault(); toggleFs(); }
    else if (ev.key === 'Escape' && pseudoFs) exitFs();   // the real API handles Esc itself
  });

  seek(0);
  requestAnimationFrame(frame);

  // autoplay the first time the demo scrolls into view
  if ('IntersectionObserver' in window) {
    var started = false;
    var ao = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting && !started) { started = true; setPlaying(true); ao.disconnect(); }
    }, { threshold: 0.35 });
    ao.observe($('#mat'));
  }

  // expose a tiny hook for automated checks
  window.RaidReplay = { seek: seek, play: function () { setPlaying(true); }, pause: function () { setPlaying(false); }, speed: function (s) { speed = s; }, fullscreen: toggleFs, diff: DIFF, events: N, state: function () { return { idx: idx, home: S.mat[HOME.id].length, away: S.mat[AWAY.id].length }; } };
})();
