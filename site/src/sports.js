/* Multi-sport section: one showcase match per discovered sport, driven ONLY by its converted JSON-LD.
   The page rebuilds the native match from the JSON-LD with a generic reader (a mirror of
   engine/converter.py from_graph, driven by the sport's field tables) and compares it, field by field,
   with the original JSON: that is the "diff = 0" badge. */
(function () {
  'use strict';
  var SP = window.RR_SPORTS;
  if (!SP || !Object.keys(SP).length) return;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) { return String(s).replace(/\s*\(fictional\)/gi, '').replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var arr = function (v) { return v == null ? [] : Array.isArray(v) ? v : [v]; };
  var fmt = function (n) { return Number(n).toLocaleString('en-IN'); };
  var SPORTNS = 'https://sportschema.org/ontologies/main/', RDFS = 'http://www.w3.org/2000/01/rdf-schema#';
  var WIN = 'http://cv.iptc.org/newscodes/speventoutcome/win';

  /* ---------------- generic JSON-LD reader ---------------- */
  function reader(doc) {
    var ctx = doc['@context'] || {};
    var expand = function (s) {
      if (typeof s !== 'string') return s;
      var i = s.indexOf(':');
      if (i > 0 && ctx[s.slice(0, i)] && s.slice(i + 1, i + 3) !== '//') return ctx[s.slice(0, i)] + s.slice(i + 1);
      return s;
    };
    var nodes = {};
    (doc['@graph'] || []).forEach(function (n) {
      var o = { '@id': expand(n['@id']), '@type': arr(n['@type']).map(expand) };
      Object.keys(n).forEach(function (k) { if (k[0] !== '@') o[expand(k)] = n[k]; });
      nodes[o['@id']] = o;
    });
    var val = function (v) { return v && typeof v === 'object' && '@value' in v ? v['@value'] : v; };
    var ref = function (v) { return v && typeof v === 'object' ? expand(v['@id']) : expand(v); };
    var node = function (v) { return nodes[ref(v)]; };
    return { nodes: nodes, val: val, ref: ref, node: node, expand: expand };
  }

  function rebuild(sp) {
    var R = reader(sp.jsonld), T = sp.tables, nid = sp.native_id;
    var all = Object.keys(R.nodes).map(function (k) { return R.nodes[k]; });
    var is = function (t) { return function (n) { return n['@type'].indexOf(t) >= 0; }; };
    var get = function (n, p) { return R.val(arr(n[p])[0]); };
    var strint = function (v) { return typeof v === 'string' && /^-?\d+$/.test(v) ? parseInt(v, 10) : v; };
    var ev = all.filter(is(SPORTNS + 'Event'))[0];
    var tpTeam = {};
    function read(n, table) {
      var out = {};
      table.forEach(function (row) {
        var key = row[0], p = row[1], kind = row[2], v = n[p];
        if (v === undefined) return;
        if (kind === 'players') { out[key] = arr(v).map(function (x) { return get(R.node(x), nid); }).sort(); return; }
        v = arr(v)[0];
        if (kind === 'lit') out[key] = R.val(v);
        else if (kind === 'strint') out[key] = strint(R.val(v));
        else if (kind === 'player' || kind === 'team' || kind === 'event') out[key] = get(R.node(v), nid);
        else if (kind === 'teampart') out[key] = tpTeam[R.ref(v)];
        else if (kind === 'concept') { var iri = R.ref(v); out[key] = iri.indexOf(row[3]) === 0 ? iri.slice(row[3].length) : iri; }
      });
      return out;
    }
    var match = { id: get(ev, nid), name: get(ev, RDFS + 'label'), start: get(ev, SPORTNS + 'startDateTime') };
    var comp = ev[SPORTNS + 'eventInCompetition'], site = ev[SPORTNS + 'location'];
    if (comp) { var c = R.node(comp); match.competition = { id: get(c, nid), name: get(c, RDFS + 'label') }; }
    if (site) { var s = R.node(site); match.venue = { id: get(s, nid), name: get(s, RDFS + 'label') }; }
    var teams = [], scores = {}, result = {};
    arr(ev[SPORTNS + 'participation']).forEach(function (r) {
      var tp = R.node(r), team = R.node(tp[SPORTNS + 'participationBy']);
      var tid = get(team, nid);
      tpTeam[tp['@id']] = tid;
      var t = { id: tid, name: get(team, RDFS + 'label') };
      var side = get(tp, SPORTNS + 'alignment');
      if (side !== undefined) t.side = side;
      var tf = read(team, T.team);
      Object.keys(tf).forEach(function (k) { t[k] = tf[k]; });
      teams.push(t);
      scores[tid] = strint(get(tp, SPORTNS + 'score'));
      if (R.ref(arr(tp[SPORTNS + 'eventOutcome'])[0]) === WIN) result.winner = tid;
    });
    teams.sort(function (a, b) { return a.id < b.id ? -1 : 1; });
    var mf = read(ev, T.match); Object.keys(mf).forEach(function (k) { match[k] = mf[k]; });
    result.scores = scores;
    var rf = read(ev, T.result); Object.keys(rf).forEach(function (k) { result[k] = rf[k]; });
    var players = [];
    all.filter(is(SPORTNS + 'IndividualParticipation')).forEach(function (ip) {
      var tid = tpTeam[R.ref(arr(ip[SPORTNS + 'teamParticipation'])[0])];
      if (tid === undefined) return;
      var a = R.node(ip[SPORTNS + 'participationBy']);
      var p = { id: get(a, nid), name: get(a, RDFS + 'label'), team: tid };
      var pf = read(ip, T.player); Object.keys(pf).forEach(function (k) { p[k] = pf[k]; });
      players.push(p);
    });
    players.sort(function (a, b) { return a.id < b.id ? -1 : 1; });
    var classOf = {}; Object.keys(T.classes).forEach(function (t) { classOf[T.classes[t]] = t; });
    var events = all.filter(is(SPORTNS + 'Action')).filter(function (n) { return R.ref(arr(n[SPORTNS + 'actionInEvent'])[0]) === ev['@id']; })
      .map(function (n) {
        var t = n['@type'].map(function (c) { return classOf[c]; }).filter(Boolean)[0];
        var e = { id: get(n, nid), seq: strint(get(n, SPORTNS + 'sequenceNumber')), type: t };
        var f = read(n, T.common.concat(T.events[t] || []));
        Object.keys(f).forEach(function (k) { e[k] = f[k]; });
        return e;
      }).sort(function (a, b) { return a.seq - b.seq; });
    return { format: sp.original.format, match: match, teams: teams, players: players, events: events, result: result };
  }

  // every leaf compared strictly: 2 !== "2", false !== 0, missing !== present
  function leafDiff(a, b) {
    var r = { fields: 0, diffs: 0 };
    (function walk(x, y) {
      var xo = x !== null && typeof x === 'object', yo = y !== null && typeof y === 'object';
      if (Array.isArray(x) || Array.isArray(y)) {
        if (!Array.isArray(x) || !Array.isArray(y)) { r.fields++; r.diffs++; return; }
        if (!x.length && !y.length) { r.fields++; return; }
        for (var i = 0; i < Math.max(x.length, y.length); i++) walk(x[i], y[i]);
        return;
      }
      if (xo || yo) {
        if (!xo || !yo) { r.fields++; r.diffs++; return; }
        var keys = {}; Object.keys(x).concat(Object.keys(y)).forEach(function (k) { keys[k] = 1; });
        Object.keys(keys).forEach(function (k) { if (!(k in x) || !(k in y)) { r.fields++; r.diffs++; } else walk(x[k], y[k]); });
        return;
      }
      r.fields++; if (x !== y) r.diffs++;
    })(a, b);
    return r;
  }

  /* ---------------- rendering ---------------- */
  var COL = ['#C2410C', '#3730A3'];
  function teamInfo(m) {
    var order = m.teams.slice().sort(function (a, b) {
      var sa = a.side === 'home' || a.side === 'A' ? 0 : 1, sb = b.side === 'home' || b.side === 'A' ? 0 : 1;
      return sa - sb || (a.id < b.id ? -1 : 1);
    });
    var info = {};
    order.forEach(function (t, i) { info[t.id] = { t: t, c: COL[i], short: t.short || t.id }; });
    return { order: order, info: info };
  }
  var pname = function (m) { var p = {}; m.players.forEach(function (x) { p[x.id] = x.name; }); return function (id) { return p[id] || id; }; };
  var chip = function (ti, tid, text) { var i = ti.info[tid]; return '<span class="sp-chip" style="--c:' + (i ? i.c : '#666') + '">' + esc(text || (i ? i.short : tid)) + '</span>'; };

  function renderValorant(m, ti) {
    var P = pname(m), ev = m.events, out = [];
    var byRound = {};
    ev.forEach(function (e) { if (e.round !== undefined) (byRound[e.round] = byRound[e.round] || []).push(e); });
    ev.forEach(function (e) {
      if (e.type === 'half_start') out.push('<div class="sp-divider">' + (e.half === 1 ? 'First half' : e.half === 2 ? 'Sides switch · second half' : 'Overtime · sides switch every round') + '</div>');
      if (e.type !== 'round') return;
      var evs = byRound[e.round] || [], kills = evs.filter(function (x) { return x.type === 'kill'; });
      var plant = evs.filter(function (x) { return x.type === 'plant'; })[0], defuse = evs.filter(function (x) { return x.type === 'defuse'; })[0];
      var feed = kills.map(function (k) {
        var kt = (m.players.filter(function (p) { return p.id === k.killer; })[0] || {}).team;
        return { t: k.time, s: k.seq, html: '<li><span class="sp-t">' + k.time + 's</span>' + chip(ti, kt, P(k.killer)) + ' <span class="sp-x">✕</span> ' + esc(P(k.victim)) +
          ' <span class="sp-dim">' + esc(k.weapon) + (k.headshot ? ' · headshot' : '') + (k.assists ? ' · assist ' + k.assists.map(P).map(esc).join(', ') : '') + '</span></li>' };
      });
      if (plant) feed.push({ t: plant.time, s: plant.seq, html: '<li><span class="sp-t">' + plant.time + 's</span><span class="sp-tag">SPIKE PLANTED · ' + esc(plant.site) + '</span> ' + esc(P(plant.planter)) + '</li>' });
      if (defuse) feed.push({ t: defuse.time, s: defuse.seq, html: '<li><span class="sp-t">' + defuse.time + 's</span><span class="sp-tag sp-tag2">DEFUSED</span> ' + esc(P(defuse.defuser)) + '</li>' });
      feed.sort(function (a, b) { return a.t - b.t || a.s - b.s; });
      feed = feed.map(function (f) { return f.html; });
      var h = ti.order[0].id, a = ti.order[1].id;
      var sc = (ti.order[0].side === 'home' ? [e.home_score, e.away_score] : [e.away_score, e.home_score]);
      out.push('<details class="sp-row"><summary><span class="sp-n">R' + e.round + '</span>' + chip(ti, e.winner) +
        '<span class="sp-cond">' + esc(e.win_condition.replace(/-/g, ' ')) + '</span>' +
        '<span class="sp-meta">' + kills.length + ' kills' + (plant ? ' · plant ' + esc(plant.site) : '') + ' · ' + esc(ti.info[e.attack].short) + ' attack</span>' +
        '<span class="sp-score">' + sc[0] + '–' + sc[1] + '</span></summary><ul class="sp-feed">' + feed.join('') + '</ul></details>');
    });
    return out.join('');
  }

  function renderBadminton(m, ti) {
    var out = [], games = {};
    m.events.forEach(function (e) { if (e.game !== undefined) (games[e.game] = games[e.game] || []).push(e); });
    var sideOf = {}; m.players.forEach(function (p) { sideOf[p.id] = (ti.info[p.team].t.side === 'A' || ti.info[p.team].t.side === 'home') ? 0 : 1; });
    Object.keys(games).sort().forEach(function (g) {
      var evs = games[g], end = evs.filter(function (e) { return e.type === 'game_end'; })[0];
      var rallies = evs.filter(function (e) { return e.type === 'rally' || e.type === 'fault'; });
      var dots = rallies.map(function (r) {
        var s = sideOf[r.winner];
        return '<i class="sp-dot' + (r.type === 'fault' ? ' sp-fault' : '') + '" style="--c:' + COL[s] + '" title="Rally ' + r.rally + ': ' + r.score_a + '–' + r.score_b +
          (r.shot ? ' · ' + esc(r.shot) : '') + (r.fault ? ' · fault: ' + esc(r.fault) : '') + '"></i>';
      }).join('');
      var interval = evs.filter(function (e) { return e.type === 'interval'; })[0];
      out.push('<div class="sp-game"><div class="sp-ghead"><b>Game ' + g + '</b>' + (end ? '<span class="sp-score">' + end.score_a + '–' + end.score_b + '</span>' + chip(ti, (m.players.filter(function (p) { return p.id === end.winner; })[0] || {}).team, end.winner && pname(m)(end.winner)) : '') +
        '<span class="sp-meta">' + rallies.length + ' rallies' + (interval ? ' · interval at ' + interval.score_a + '–' + interval.score_b : '') + '</span></div><div class="sp-dots">' + dots + '</div></div>');
    });
    return out.join('');
  }

  function renderKhokho(m, ti) {
    var P = pname(m), out = [], turns = {};
    m.events.forEach(function (e) { if (e.turn !== undefined) (turns[e.turn] = turns[e.turn] || []).push(e); });
    Object.keys(turns).sort(function (a, b) { return a - b; }).forEach(function (t) {
      var evs = turns[t], sum = evs.filter(function (e) { return e.type === 'turn'; })[0], tags = evs.filter(function (e) { return e.type === 'tag'; });
      var end = evs.filter(function (e) { return e.type === 'turn_end'; })[0];
      out.push('<details class="sp-row"' + (t === '1' ? ' open' : '') + '><summary><span class="sp-n">T' + t + '</span>' + (sum ? chip(ti, sum.chasing) + '<span class="sp-cond">chasing</span>' : '') +
        '<span class="sp-meta">' + tags.length + ' tags' + (end ? ' · ' + end.time + ' s' : '') + '</span><span class="sp-score">+' + (sum ? sum.points : 0) + '</span></summary><ul class="sp-feed">' +
        tags.map(function (g) {
          return '<li><span class="sp-t">' + g.time + 's</span>' + chip(ti, sum && sum.chasing, P(g.tagger)) + ' <span class="sp-x">→</span> ' + esc(P(g.defender)) +
            ' <span class="sp-dim">' + esc(String(g.method).replace(/-/g, ' ')) + ' · batch ' + g.batch + ' · +' + g.points + '</span></li>';
        }).join('') + '</ul></details>');
    });
    return out.join('');
  }

  function renderGeneric(m) {
    return '<ul class="sp-feed">' + m.events.slice(0, 60).map(function (e) { return '<li><span class="sp-t">#' + e.seq + '</span>' + esc(e.type) + '</li>'; }).join('') + '</ul>';
  }
  var RENDER = { valorant: renderValorant, badminton: renderBadminton, khokho: renderKhokho };

  function show(name) {
    var sp = SP[name], m = rebuild(sp), d = leafDiff(sp.original, m), ti = teamInfo(m);
    document.querySelectorAll('.sp-switch button').forEach(function (b) { b.setAttribute('aria-selected', b.dataset.sport === name); });
    var w = m.result.winner;
    $('#spBoard').innerHTML = ti.order.map(function (t) {
      return '<div class="sp-team' + (t.id === w ? ' win' : '') + '"><span class="sw" style="background:' + ti.info[t.id].c + '"></span><b>' + esc(t.name) + '</b><em>' + m.result.scores[t.id] + '</em></div>';
    }).join('');
    $('#spMeta').innerHTML = esc(m.match.name) + ' · ' + esc((m.match.competition || {}).name || '') + (m.match.map ? ' · map ' + esc(m.match.map) : '') +
      (m.match.purpose ? ' · ' + esc(m.match.purpose) : '');
    $('#spAbout').textContent = sp.about;
    var badge = $('#spDiff');
    badge.textContent = 'diff = ' + d.diffs + (d.diffs ? ' ✕' : ' ✓');
    badge.classList.toggle('bad', d.diffs !== 0);
    $('#spDiffSmall').textContent = fmt(d.fields) + ' fields of the original JSON compared with the match rebuilt from ' + fmt(sp.triples) + ' RDF triples (JSON-LD), ' + m.events.length + ' events';
    $('#spTimeline').innerHTML = (RENDER[name] || renderGeneric)(m, ti);
    window.RaidReplaySports.current = { sport: name, diff: d, events: m.events.length, scores: m.result.scores };
  }

  var names = Object.keys(SP);
  $('#spSwitch').innerHTML = names.map(function (n, i) {
    return '<button role="tab" data-sport="' + n + '" aria-selected="' + (i === 0) + '">' + esc(SP[n].label) + '</button>';
  }).join('');
  document.querySelectorAll('.sp-switch button').forEach(function (b) { b.addEventListener('click', function () { show(b.dataset.sport); }); });
  window.RaidReplaySports = { show: show, sports: names, current: null,
    rebuild: function (n) { return rebuild(SP[n]); }, diff: function (n) { return leafDiff(SP[n].original, rebuild(SP[n])); },
    diffAll: function () { var o = {}; names.forEach(function (n) { o[n] = leafDiff(SP[n].original, rebuild(SP[n])); }); return o; } };
  show(names[0]);
})();
