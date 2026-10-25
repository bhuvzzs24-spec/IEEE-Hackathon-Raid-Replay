/* Sport selector (top of page) + animated stage for the other sports, driven by the JSON-LD rebuilt in sports.js. */
(function () {
  'use strict';
  var API = window.RaidReplaySports, SP = window.RR_SPORTS;
  if (!API || !SP) return;
  var NS = 'http://www.w3.org/2000/svg', $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var COL = ['#C2410C', '#3730A3'];

  // ---------- selector bar ----------
  var bar = document.createElement('div');
  bar.className = 'sport-bar';
  bar.innerHTML = '<div class="wrap sport-bar-in"><span class="sb-l">Sport</span>' +
    ['kabaddi'].concat(API.sports).map(function (n) {
      return '<button data-s="' + n + '" aria-pressed="' + (n === 'kabaddi') + '">' + esc(n === 'kabaddi' ? 'Kabaddi' : SP[n].label) + '</button>';
    }).join('') + '</div>';
  var main = $('#top');
  main.parentNode.insertBefore(bar, main);
  var stageSec = document.createElement('section');
  stageSec.className = 'sec stage-sec'; stageSec.id = 'stage';
  stageSec.innerHTML = '<div class="wrap"><p class="eyebrow" id="stEyebrow"></p><h2 id="stTitle"></h2><p class="intro" id="stIntro"></p>' +
    '<div class="st-wrap"><div class="st-hud"><div class="st-team" id="stA"></div><div class="st-mid"><b id="stClock"></b><span id="stSub"></span></div><div class="st-team st-r" id="stB"></div></div>' +
    '<svg id="stSvg" viewBox="0 0 960 520" role="img" aria-label="Animated replay"></svg>' +
    '<div class="st-com" id="stCom">Press play.</div>' +
    '<div class="st-ctl"><button id="stPlay">▶ Play</button><button id="stRestart">⟲ Restart</button>' +
    '<span class="st-speed">' + [1, 2, 4, 8].map(function (s) { return '<button data-sp="' + s + '"' + (s === 2 ? ' class="on"' : '') + '>' + s + '×</button>'; }).join('') + '</span>' +
    '<input type="range" id="stScrub" min="0" value="0" aria-label="Scrub"><span class="st-n" id="stN"></span>' +
    '<span class="ok-badge" id="stDiff"></span></div></div></div>';
  var sportsSec = $('#sports');
  sportsSec.parentNode.insertBefore(stageSec, sportsSec);

  var svg = $('#stSvg'), speed = 2, playing = false, timer = null, steps = [], idx = 0, cur = null, el = {};
  function node(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (parent || svg).appendChild(n); return n;
  }
  function piece(id, x, y, fill, label, r) {
    var g = el[id];
    if (!g) {
      g = node('g', { 'class': 'st-p' }); node('circle', { r: r || 16, fill: fill, stroke: '#fff', 'stroke-width': 2.5 }, g);
      var t = node('text', { 'text-anchor': 'middle', dy: '0.35em', 'class': 'st-pl' }, g); t.textContent = label || '';
      el[id] = g;
    }
    g.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    g.classList.remove('dead');
    return g;
  }
  function flash(x1, y1, x2, y2, color) {
    var l = node('line', { x1: x1, y1: y1, x2: x2, y2: y2, stroke: color, 'stroke-width': 4, 'class': 'st-flash' });
    setTimeout(function () { l.remove(); }, 900);
  }
  function banner(text, color) {
    var g = node('g', { 'class': 'st-banner' });
    node('rect', { x: 280, y: 222, width: 400, height: 76, fill: color || '#1B1E23', rx: 2 }, g);
    var t = node('text', { x: 480, y: 268, 'text-anchor': 'middle', 'class': 'st-bt' }, g); t.textContent = text;
    setTimeout(function () { g.remove(); }, 1300 / Math.sqrt(speed));
  }
  var posOf = function (id) { var g = el[id]; if (!g) return [480, 260]; var m = /translate\(([-\d.]+)px,\s*([-\d.]+)px/.exec(g.style.transform); return m ? [+m[1], +m[2]] : [480, 260]; };

  // ---------- per-sport stage builders: return {setup(), steps:[{ms, run()}]} ----------
  function teamColours(m) {
    var ti = {}; var order = m.teams.slice().sort(function (a, b) { var sa = (a.side === 'home' || a.side === 'A') ? 0 : 1, sb = (b.side === 'home' || b.side === 'A') ? 0 : 1; return sa - sb; });
    order.forEach(function (t, i) { ti[t.id] = { c: COL[i], i: i, t: t }; }); return { ti: ti, order: order };
  }
  var pn = function (m) { var p = {}; m.players.forEach(function (x) { p[x.id] = x; }); return p; };

  function valorant(m, H) {
    var T = teamColours(m), P = pn(m), sites = { A: [760, 120], B: [760, 400], C: [560, 70] };
    var rounds = {}; m.events.forEach(function (e) { if (e.round !== undefined) (rounds[e.round] = rounds[e.round] || []).push(e); });
    function setup() {
      svg.innerHTML = ''; el = {};
      node('rect', { x: 10, y: 10, width: 940, height: 500, fill: '#20252c' });
      ['A', 'B'].concat(m.match.map === 'Haven' ? ['C'] : []).forEach(function (s) {
        node('rect', { x: sites[s][0] - 70, y: sites[s][1] - 55, width: 140, height: 110, fill: 'none', stroke: '#e7c66b', 'stroke-dasharray': '8 6', 'stroke-width': 2 });
        var t = node('text', { x: sites[s][0], y: sites[s][1] + 6, 'text-anchor': 'middle', 'class': 'st-site' }); t.textContent = s;
      });
      node('rect', { x: 30, y: 200, width: 120, height: 120, fill: 'rgba(255,255,255,.04)' });
      var t = node('text', { x: 90, y: 340, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'ATTACKER SPAWN';
      var t2 = node('text', { x: 920, y: 500, 'text-anchor': 'end', 'class': 'st-lbl' }); t2.textContent = 'map ' + m.match.map + ' · positions illustrative';
    }
    var st = [];
    Object.keys(rounds).map(Number).sort(function (a, b) { return a - b; }).forEach(function (r) {
      var evs = rounds[r], sum = evs.filter(function (e) { return e.type === 'round'; })[0];
      if (!sum) return;
      var att = sum.attack, target = (evs.filter(function (e) { return e.type === 'plant'; })[0] || {}).site || (r % 2 ? 'A' : 'B');
      st.push({ ms: 900, run: function () {
        Object.keys(el).forEach(function (k) { if (el[k].classList.contains('st-p')) el[k].remove(); }); el = {};
        Object.keys(P).forEach(function (pid, i) {
          var p = P[pid], a = p.team === att, k = Object.keys(P).filter(function (q) { return P[q].team === p.team; }).indexOf(pid);
          piece(pid, a ? 70 + (k % 2) * 40 : 680 + (k % 2) * 90, a ? 215 + k * 22 : 120 + k * 70, T.ti[p.team].c, (p.name || pid).slice(0, 2).toUpperCase(), 14);
        });
        H('Round ' + r, (T.ti[att] ? T.ti[att].t.short || att : att) + ' attack', 'Round ' + r + ' — ' + (T.ti[att].t.name) + ' attack; buys ' + sum.home_buy + ' / ' + sum.away_buy + '.');
      } });
      evs.filter(function (e) { return e.type !== 'round'; }).sort(function (a, b) { return a.time - b.time || a.seq - b.seq; }).forEach(function (e) {
        st.push({ ms: 700, run: function () {
          Object.keys(P).forEach(function (pid) {   // attackers creep towards the site
            if (P[pid].team === att && el[pid] && !el[pid].classList.contains('dead')) { var p = posOf(pid), s = sites[target]; piece(pid, p[0] + (s[0] - 60 - p[0]) * 0.3, p[1] + (s[1] - p[1]) * 0.3); }
          });
          if (e.type === 'kill') {
            var a = posOf(e.killer), b = posOf(e.victim);
            flash(a[0], a[1], b[0], b[1], T.ti[P[e.killer].team].c);
            el[e.victim] && el[e.victim].classList.add('dead');
            H(null, null, e.time + 's  ' + (P[e.killer].name) + ' ✕ ' + P[e.victim].name + ' · ' + e.weapon + (e.headshot ? ' · headshot' : ''));
          } else if (e.type === 'plant') {
            var s = sites[e.site]; piece(e.planter, s[0] - 20, s[1]);
            var sp = node('circle', { cx: s[0] + 20, cy: s[1], r: 10, fill: '#ef4444', 'class': 'st-spike' }); el['spike'] = sp;
            H(null, null, e.time + 's  Spike planted on ' + e.site + ' by ' + P[e.planter].name);
          } else if (e.type === 'defuse') {
            var s2 = sites[e.site]; piece(e.defuser, s2[0] + 40, s2[1]);
            el['spike'] && el['spike'].setAttribute('fill', '#22c55e');
            H(null, null, e.time + 's  DEFUSED by ' + P[e.defuser].name);
          }
        } });
      });
      st.push({ ms: 1100, run: function () {
        el['spike'] && (el['spike'].remove(), delete el['spike']);
        var sc = {}; m.teams.forEach(function (t) { sc[t.id] = t.side === 'home' ? sum.home_score : sum.away_score; });
        H(null, null, T.ti[sum.winner].t.name + ' win round ' + r + ' — ' + sum.win_condition.replace(/-/g, ' '), sc);
        banner(T.ti[sum.winner].t.short + ' WIN · ' + sum.win_condition.replace(/-/g, ' ').toUpperCase(), T.ti[sum.winner].c);
      } });
    });
    return { setup: setup, steps: st };
  }

  function badminton(m, H) {
    var T = teamColours(m), P = pn(m), sideOf = {};
    m.players.forEach(function (p) { sideOf[p.id] = T.ti[p.team].i; });
    var X = [200, 760];
    function setup() {
      svg.innerHTML = ''; el = {};
      node('rect', { x: 60, y: 90, width: 840, height: 340, fill: '#2f6b4f', stroke: '#fff', 'stroke-width': 3 });
      [[60, 130, 900, 130], [60, 390, 900, 390], [340, 90, 340, 430], [620, 90, 620, 430], [60, 260, 340, 260], [620, 260, 900, 260]].forEach(function (l) { node('line', { x1: l[0], y1: l[1], x2: l[2], y2: l[3], stroke: 'rgba(255,255,255,.7)', 'stroke-width': 2 }); });
      node('line', { x1: 480, y1: 70, x2: 480, y2: 450, stroke: '#fff', 'stroke-width': 5 });
      var t = node('text', { x: 480, y: 62, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'NET';
      m.players.forEach(function (p) { piece(p.id, X[sideOf[p.id]], 260, T.ti[p.team].c, (p.name || p.id).split(' ').map(function (w) { return w[0]; }).join('').slice(0, 2), 20); });
      el.shuttle = node('circle', { r: 7, fill: '#fff', 'class': 'st-shuttle', cx: 480, cy: 260 });
    }
    var st = [];
    m.events.forEach(function (e) {
      if (e.type === 'game_start') st.push({ ms: 900, run: function () { H('Game ' + e.game, '', 'Game ' + e.game + ' starts.'); banner('GAME ' + e.game); } });
      if (e.type === 'rally' || e.type === 'fault') st.push({ ms: 900, run: function () {
        var w = sideOf[e.winner], ys = 150 + ((e.rally * 53) % 220);
        piece(e.server, X[sideOf[e.server]], ys, T.ti[P[e.server].team].c);
        piece(e.receiver, X[sideOf[e.receiver]], 520 - ys, T.ti[P[e.receiver].team].c);
        var landX = w === 0 ? 700 : 260, landY = 120 + ((e.rally * 97) % 280);
        el.shuttle.setAttribute('cx', landX); el.shuttle.setAttribute('cy', landY);
        el.shuttle.setAttribute('fill', e.type === 'fault' ? '#ef4444' : '#fff');
        var sc = {}; m.teams.forEach(function (t) { sc[t.id] = T.ti[t.id].i === 0 ? e.score_a : e.score_b; });
        H('Game ' + e.game, 'rally ' + e.rally, P[e.winner].name + ' wins rally ' + e.rally + (e.shot ? ' with a ' + e.shot.replace(/-/g, ' ') : '') + (e.fault ? ' — fault: ' + e.fault.replace(/-/g, ' ') : '') + '  (' + e.score_a + '–' + e.score_b + ', ' + e.length + ' shots)', sc);
      } });
      if (e.type === 'game_end') st.push({ ms: 1400, run: function () { banner('GAME ' + e.game + ' · ' + e.score_a + '–' + e.score_b + ' · ' + P[e.winner].name.toUpperCase(), T.ti[P[e.winner].team].c); } });
    });
    return { setup: setup, steps: st };
  }

  function khokho(m, H) {
    var T = teamColours(m), P = pn(m), score = {};
    m.teams.forEach(function (t) { score[t.id] = 0; });
    var turns = {}; m.events.forEach(function (e) { if (e.turn !== undefined) (turns[e.turn] = turns[e.turn] || []).push(e); });
    function setup() {
      svg.innerHTML = ''; el = {};
      node('rect', { x: 40, y: 60, width: 880, height: 400, fill: '#a8794b', stroke: '#fff', 'stroke-width': 3 });
      node('line', { x1: 120, y1: 260, x2: 840, y2: 260, stroke: '#fff', 'stroke-width': 2 });
      [120, 840].forEach(function (x) { node('rect', { x: x - 6, y: 245, width: 12, height: 30, fill: '#3b2a1a' }); });
      for (var i = 0; i < 8; i++) node('rect', { x: 180 + i * 85 - 12, y: 248, width: 24, height: 24, fill: 'rgba(255,255,255,.25)' });
      var t = node('text', { x: 480, y: 52, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'CENTRAL LANE · 8 SEATED CHASERS · POLES AT BOTH ENDS · positions illustrative';
    }
    var st = [];
    Object.keys(turns).map(Number).sort(function (a, b) { return a - b; }).forEach(function (tn) {
      var evs = turns[tn], sum = evs.filter(function (e) { return e.type === 'turn'; })[0]; if (!sum) return;
      var chasers = m.players.filter(function (p) { return p.team === sum.chasing; }).slice(0, 9);
      var defs = m.players.filter(function (p) { return p.team === sum.defending; });
      st.push({ ms: 1200, run: function () {
        Object.keys(el).forEach(function (k) { if (el[k].classList && el[k].classList.contains('st-p')) el[k].remove(); }); el = {};
        chasers.forEach(function (p, i) { piece(p.id, i < 8 ? 180 + i * 85 : 100, i < 8 ? 260 : 200, T.ti[p.team].c, String(p.jersey || ''), 14); });
        defs.filter(function (p) { return p.batch === 1; }).forEach(function (p, i) { piece(p.id, 300 + i * 160, 140 + (i % 2) * 240, T.ti[p.team].c, String(p.jersey || ''), 14); });
        H('Turn ' + tn, T.ti[sum.chasing].t.short + ' chasing', 'Turn ' + tn + ': ' + T.ti[sum.chasing].t.name + ' chase, ' + T.ti[sum.defending].t.name + ' defend.', score);
        banner('TURN ' + tn + ' · ' + T.ti[sum.chasing].t.short + ' CHASE', T.ti[sum.chasing].c);
      } });
      evs.filter(function (e) { return e.type === 'tag'; }).forEach(function (g, k) {
        st.push({ ms: 900, run: function () {
          var d = el[g.defender] ? posOf(g.defender) : [300 + (k % 4) * 140, 120 + (k % 3) * 140];
          if (!el[g.defender]) piece(g.defender, d[0], d[1], T.ti[sum.defending].c, String(P[g.defender].jersey || ''), 14);
          piece(g.tagger, d[0] - 22, d[1], T.ti[sum.chasing].c, String(P[g.tagger].jersey || ''), 14);
          flash(d[0] - 22, d[1], d[0], d[1], '#fff');
          setTimeout(function () { el[g.defender] && el[g.defender].classList.add('dead'); }, 200);
          score[sum.chasing] += g.points;
          H(null, g.time + 's', P[g.tagger].name + ' tags ' + P[g.defender].name + ' — ' + String(g.method).replace(/-/g, ' ') + ' (+' + g.points + ')', score);
        } });
      });
    });
    return { setup: setup, steps: st };
  }
  var BUILD = { valorant: valorant, badminton: badminton, khokho: khokho };

  // ---------- player ----------
  var current = null, model = null, built = null, scoreNow = {};
  function hud(clock, sub, text, sc) {
    if (clock !== null && clock !== undefined) $('#stClock').textContent = clock;
    if (sub !== null && sub !== undefined) $('#stSub').textContent = sub;
    if (text) $('#stCom').textContent = text;
    if (sc) scoreNow = sc;
    var T = teamColours(model);
    [$('#stA'), $('#stB')].forEach(function (box, i) {
      var t = T.order[i]; box.innerHTML = '<span class="sw" style="background:' + COL[i] + '"></span><span>' + esc(t.name) + '</span><b>' + (scoreNow[t.id] !== undefined ? scoreNow[t.id] : 0) + '</b>';
    });
  }
  function stop() { playing = false; clearTimeout(timer); $('#stPlay').textContent = '▶ Play'; }
  function tick() {
    if (!playing) return;
    if (idx >= steps.length) { stop(); hud(null, 'full time', 'Full time: ' + model.teams.map(function (t) { return t.name + ' ' + model.result.scores[t.id]; }).join(' – '), model.result.scores); return; }
    steps[idx].run(); idx++; $('#stScrub').value = idx; $('#stN').textContent = idx + ' / ' + steps.length;
    timer = setTimeout(tick, steps[idx - 1].ms / speed);
  }
  function load(name) {
    stop(); current = name; model = API.rebuild(name); scoreNow = {};
    model.teams.forEach(function (t) { scoreNow[t.id] = 0; });
    built = BUILD[name](model, hud); steps = built.steps; idx = 0; built.setup();
    $('#stScrub').max = steps.length; $('#stScrub').value = 0; $('#stN').textContent = '0 / ' + steps.length;
    var d = API.diff(name);
    $('#stDiff').textContent = 'diff = ' + d.diffs + (d.diffs ? ' ✕' : ' ✓') + ' · from JSON-LD';
    $('#stEyebrow').textContent = SP[name].label + ' · live replay';
    $('#stTitle').textContent = model.match.name + ' — replayed from Sport Schema data only';
    $('#stIntro').textContent = (model.match.competition ? model.match.competition.name + '. ' : '') + 'Every move on this ' + (name === 'valorant' ? 'map' : name === 'badminton' ? 'court' : 'field') +
      ' is read from the converted JSON-LD (' + model.events.length + ' events); the in-page check compares it with the original JSON field by field.';
    hud('Ready', '', 'Press play.', scoreNow);
  }
  function seek(k) {
    var was = playing; stop(); built.setup(); scoreNow = {}; model.teams.forEach(function (t) { scoreNow[t.id] = 0; });
    if (name === 'khokho') {}
    var saved = speed; speed = 1000; for (idx = 0; idx < k; idx++) steps[idx].run(); speed = saved;
    document.querySelectorAll('.st-flash,.st-banner').forEach(function (n) { n.remove(); });
    $('#stN').textContent = idx + ' / ' + steps.length; if (was) { playing = true; tick(); }
  }
  var name = null;
  $('#stPlay').addEventListener('click', function () { if (playing) stop(); else { if (idx >= steps.length) seek(0); playing = true; $('#stPlay').textContent = '❚❚ Pause'; tick(); } });
  $('#stRestart').addEventListener('click', function () { seek(0); });
  $('#stScrub').addEventListener('input', function () { seek(parseInt(this.value, 10)); });
  document.querySelectorAll('.st-speed button').forEach(function (b) { b.addEventListener('click', function () { speed = +b.dataset.sp; document.querySelectorAll('.st-speed button').forEach(function (x) { x.classList.toggle('on', x === b); }); }); });

  function select(s) {
    name = s;
    document.querySelectorAll('.sport-bar button').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.s === s); });
    document.body.classList.toggle('mode-other', s !== 'kabaddi');
    if (s !== 'kabaddi') { load(s); API.show(s); stageSec.scrollIntoView ? window.scrollTo({ top: 0 }) : 0; }
    else stop();
  }
  bar.querySelectorAll('button').forEach(function (b) { b.addEventListener('click', function () { select(b.dataset.s); }); });
  window.RaidReplayStage = { select: select, play: function () { $('#stPlay').click(); }, state: function () { return { sport: name, idx: idx, steps: steps.length }; } };
})();
