/* Sport selector (top of page) + animated stage for the other sports, driven by the JSON-LD rebuilt in sports.js.
   Every event shown comes from the converted data; player positions are illustrative (the data has none). */
(function () {
  'use strict';
  var API = window.RaidReplaySports, SP = window.RR_SPORTS;
  if (!API || !SP) return;
  var NS = 'http://www.w3.org/2000/svg', $ = function (s) { return document.querySelector(s); };
  var clean = function (x) { return String(x == null ? '' : x).replace(/\s*\(fictional\)/gi, ''); };
  var esc = function (s) { return clean(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var rnd = function (seed) { var x = Math.sin(seed * 9301 + 49297) * 233280; return x - Math.floor(x); };   // deterministic jitter
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
    '<span class="ok-badge" id="stDiff"></span></div></div>' +
    '<div class="tabs st-code" id="stCode"><div class="tab-bar" role="tablist">' +
    '<button role="tab" aria-selected="true" data-st="json">Native JSON</button><button role="tab" aria-selected="false" data-st="turtle">Sport Schema · Turtle</button>' +
    '<button role="tab" aria-selected="false" data-st="jsonld">Sport Schema · JSON-LD</button><span class="tab-note" id="stNote"></span></div>' +
    '<div class="tab-panels"><pre class="code tab-panel active" data-p="json"><code></code></pre><pre class="code tab-panel" data-p="turtle"><code></code></pre>' +
    '<pre class="code tab-panel" data-p="jsonld"><code></code></pre></div></div></div>';
  stageSec.querySelectorAll('#stCode .tab-bar button').forEach(function (b) {
    b.addEventListener('click', function () {
      stageSec.querySelectorAll('#stCode .tab-bar button').forEach(function (x) { x.setAttribute('aria-selected', x === b); });
      stageSec.querySelectorAll('#stCode .tab-panel').forEach(function (p) { p.classList.toggle('active', p.dataset.p === b.dataset.st); });
    });
  });
  var sportsSec = $('#sports');
  sportsSec.parentNode.insertBefore(stageSec, sportsSec);

  var svg = $('#stSvg'), speed = 2, playing = false, timer = null, steps = [], idx = 0, el = {}, timers = [];
  var later = function (fn, ms) { timers.push(setTimeout(fn, ms)); };
  function node(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (parent || svg).appendChild(n); return n;
  }
  function piece(id, x, y, fill, label, r) {
    var g = el[id];
    if (!g) {
      g = node('g', { 'class': 'st-p' }); node('circle', { r: r || 16, fill: fill || '#888', stroke: '#fff', 'stroke-width': 2.5 }, g);
      var t = node('text', { 'text-anchor': 'middle', dy: '0.35em', 'class': 'st-pl' }, g); t.textContent = label || '';
      el[id] = g;
    }
    g.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    return g;
  }
  function flash(x1, y1, x2, y2, color) {
    var l = node('line', { x1: x1, y1: y1, x2: x2, y2: y2, stroke: color, 'stroke-width': 4, 'class': 'st-flash' });
    setTimeout(function () { l.remove(); }, 900);
  }
  function banner(text, color) {
    var g = node('g', { 'class': 'st-banner' });
    node('rect', { x: 230, y: 222, width: 500, height: 76, fill: color || '#1B1E23', rx: 2 }, g);
    var t = node('text', { x: 480, y: 268, 'text-anchor': 'middle', 'class': 'st-bt' }, g); t.textContent = text;
    setTimeout(function () { g.remove(); }, 1300 / Math.sqrt(speed));
  }
  var posOf = function (id) { var g = el[id]; if (!g) return [480, 260]; var m = /translate\(([-\d.]+)px,\s*([-\d.]+)px/.exec(g.style.transform); return m ? [+m[1], +m[2]] : [480, 260]; };
  var alive = function (id) { return el[id] && !el[id].classList.contains('dead'); };
  function clearPieces() { Object.keys(el).forEach(function (k) { if (el[k] && el[k].classList && el[k].classList.contains('st-p')) { el[k].remove(); delete el[k]; } }); }

  function teamColours(m) {
    var ti = {}; var order = m.teams.slice().sort(function (a, b) { var sa = (a.side === 'home' || a.side === 'A') ? 0 : 1, sb = (b.side === 'home' || b.side === 'A') ? 0 : 1; return sa - sb; });
    order.forEach(function (t, i) { ti[t.id] = { c: COL[i], i: i, t: t }; }); return { ti: ti, order: order };
  }
  var pn = function (m) { var p = {}; m.players.forEach(function (x) { p[x.id] = x; }); return p; };
  var initials = function (s) { return clean(s).split(/\s+/).map(function (w) { return w[0] || ''; }).join('').slice(0, 2).toUpperCase(); };

  // ================= VALORANT: defenders hold the sites, attackers stack and push, duels up close =================
  function valorant(m, H) {
    var T = teamColours(m), P = pn(m), sites = { A: [760, 130], B: [760, 400], C: [540, 80] };
    var siteList = ['A', 'B'].concat(m.match.map === 'Haven' ? ['C'] : []);
    var rounds = {}; m.events.forEach(function (e) { if (e.round !== undefined) (rounds[e.round] = rounds[e.round] || []).push(e); });
    function setup() {
      svg.innerHTML = ''; el = {};
      node('rect', { x: 10, y: 10, width: 940, height: 500, fill: '#20252c' });
      node('path', { d: 'M150 230 H600 V130 H690 M600 290 V400 H690 M380 230 V80 H470', stroke: 'rgba(255,255,255,.07)', 'stroke-width': 60, fill: 'none' });
      siteList.forEach(function (s) {
        node('rect', { x: sites[s][0] - 75, y: sites[s][1] - 60, width: 150, height: 120, fill: 'rgba(231,198,107,.05)', stroke: '#e7c66b', 'stroke-dasharray': '8 6', 'stroke-width': 2 });
        var t = node('text', { x: sites[s][0], y: sites[s][1] + 12, 'text-anchor': 'middle', 'class': 'st-site' }); t.textContent = s;
      });
      node('rect', { x: 30, y: 190, width: 130, height: 140, fill: 'rgba(255,255,255,.04)' });
      var t = node('text', { x: 95, y: 350, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'ATTACKER SPAWN';
      var t2 = node('text', { x: 930, y: 500, 'text-anchor': 'end', 'class': 'st-lbl' }); t2.textContent = 'map ' + m.match.map + ' · positions illustrative';
    }
    var st = [];
    Object.keys(rounds).map(Number).sort(function (a, b) { return a - b; }).forEach(function (r) {
      var evs = rounds[r], sum = evs.filter(function (e) { return e.type === 'round'; })[0];
      if (!sum) return;
      var att = sum.attack, plantEv = evs.filter(function (e) { return e.type === 'plant'; })[0];
      var target = plantEv ? plantEv.site : siteList[r % siteList.length];
      st.push({ ms: 1000, run: function () {
        clearPieces(); delete el.spike;
        Object.keys(P).forEach(function (pid) {
          var p = P[pid], k = Object.keys(P).filter(function (q) { return P[q].team === p.team; }).indexOf(pid);
          if (p.team === att) piece(pid, 55 + rnd(r * 13 + k) * 80, 200 + k * 28, T.ti[p.team].c, initials(p.name), 14);
          else { var s0 = sites[siteList[k % siteList.length]]; piece(pid, s0[0] - 50 + rnd(r * 11 + k) * 100, s0[1] - 45 + rnd(r * 7 + k) * 90, T.ti[p.team].c, initials(p.name), 14); }
          el[pid].classList.remove('dead');
        });
        H('Round ' + r, (T.ti[att].t.short || att) + ' attack · buys ' + sum.home_buy + ' / ' + sum.away_buy,
          'Round ' + r + ': ' + clean(T.ti[att].t.name) + ' attack, ' + clean(T.ti[sum.winner === att ? (m.teams.filter(function (t) { return t.id !== att; })[0].id) : sum.winner].t.name) + ' hold the sites.');
      } });
      var stepN = 0;
      evs.filter(function (e) { return e.type !== 'round'; }).sort(function (a, b) { return a.time - b.time || a.seq - b.seq; }).forEach(function (e) {
        stepN++;
        var push = Math.min(1, 0.3 + stepN * 0.17);
        st.push({ ms: 850, run: function () {
          Object.keys(P).forEach(function (pid, k) {   // attackers stack up and push into the target site
            if (P[pid].team === att && alive(pid)) {
              var s1 = sites[target];
              piece(pid, 120 + (s1[0] - 160) * push + rnd(k + stepN * 3) * 50, 260 + (s1[1] - 260) * push + (rnd(k * 3 + stepN) - 0.5) * 80);
            }
          });
          if (e.type === 'kill') {
            var b = posOf(e.victim), a0 = posOf(e.killer);
            var ax = b[0] + (a0[0] - b[0]) * 0.4, ay = b[1] + (a0[1] - b[1]) * 0.4;      // the duel happens up close
            piece(e.killer, ax, ay);
            later(function () { flash(ax, ay, b[0], b[1], T.ti[P[e.killer].team].c); if (el[e.victim]) el[e.victim].classList.add('dead'); }, 420 / Math.sqrt(speed));
            H(null, null, e.time + 's  ' + clean(P[e.killer].name) + ' ✕ ' + clean(P[e.victim].name) + ' · ' + e.weapon + (e.headshot ? ' · headshot' : '') +
              (e.assists ? ' · assist ' + e.assists.map(function (a) { return clean(P[a].name); }).join(', ') : ''));
          } else if (e.type === 'plant') {
            var s = sites[e.site]; piece(e.planter, s[0] - 18, s[1]);
            el.spike = node('circle', { cx: s[0] + 6, cy: s[1], r: 9, fill: '#ef4444', 'class': 'st-spike' });
            Object.keys(P).forEach(function (pid, k) {   // defenders rotate to retake
              if (P[pid].team !== att && alive(pid)) piece(pid, s[0] + 70 + rnd(k + r) * 60, s[1] - 70 + rnd(k * 5 + r) * 140);
            });
            H(null, null, e.time + 's  Spike planted on ' + e.site + ' by ' + clean(P[e.planter].name) + ' — defenders rotate to retake');
          } else if (e.type === 'defuse') {
            var s2 = sites[e.site]; piece(e.defuser, s2[0] + 24, s2[1]);
            if (el.spike) el.spike.setAttribute('fill', '#22c55e');
            H(null, null, e.time + 's  Spike DEFUSED by ' + clean(P[e.defuser].name));
          }
        } });
      });
      st.push({ ms: 1200, run: function () {
        if (el.spike && sum.win_condition === 'spike-detonated') { el.spike.setAttribute('r', 60); el.spike.setAttribute('fill', 'rgba(239,68,68,.5)'); }
        var sc = {}; m.teams.forEach(function (t) { sc[t.id] = t.side === 'home' ? sum.home_score : sum.away_score; });
        H(null, null, clean(T.ti[sum.winner].t.name) + ' win round ' + r + ' — ' + sum.win_condition.replace(/-/g, ' '), sc);
        banner(T.ti[sum.winner].t.short + ' WIN · ' + sum.win_condition.replace(/-/g, ' ').toUpperCase(), T.ti[sum.winner].c);
      } });
    });
    return { setup: setup, steps: st };
  }

  // ================= BADMINTON: multi-shot rallies, players chase the shuttle =================
  function badminton(m, H) {
    var T = teamColours(m), P = pn(m), sideOf = {};
    m.players.forEach(function (p) { sideOf[p.id] = T.ti[p.team].i; });
    var X = [230, 730];
    function setup() {
      svg.innerHTML = ''; el = {};
      node('rect', { x: 60, y: 90, width: 840, height: 340, fill: '#2f6b4f', stroke: '#fff', 'stroke-width': 3 });
      [[60, 115, 900, 115], [60, 405, 900, 405], [360, 90, 360, 430], [600, 90, 600, 430], [60, 260, 360, 260], [600, 260, 900, 260], [100, 90, 100, 430], [860, 90, 860, 430]]
        .forEach(function (l) { node('line', { x1: l[0], y1: l[1], x2: l[2], y2: l[3], stroke: 'rgba(255,255,255,.7)', 'stroke-width': 2 }); });
      node('line', { x1: 480, y1: 70, x2: 480, y2: 450, stroke: '#fff', 'stroke-width': 5 });
      var t = node('text', { x: 480, y: 62, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'NET';
      var lb = node('text', { x: 900, y: 470, 'text-anchor': 'end', 'class': 'st-lbl' }); lb.textContent = 'positions illustrative';
      m.players.forEach(function (p) { piece(p.id, X[sideOf[p.id]], 260, T.ti[p.team].c, initials(p.name), 20); });
      el.shuttle = node('circle', { r: 7, fill: '#fff', 'class': 'st-shuttle', cx: 480, cy: 260 });
    }
    var st = [];
    m.events.forEach(function (e) {
      if (e.type === 'game_start') st.push({ ms: 1000, run: function () { H('Game ' + e.game, '', 'Game ' + e.game + ' starts.'); banner('GAME ' + e.game); } });
      if (e.type === 'interval') st.push({ ms: 900, run: function () { banner('INTERVAL · ' + e.score_a + '–' + e.score_b); } });
      if (e.type === 'rally' || e.type === 'fault') {
        var shots = Math.max(2, Math.min(8, Math.round((e.length || 6) / 3)));
        st.push({ ms: 360 * shots + 450, run: function () {
          var w = sideOf[e.winner], s0 = sideOf[e.server], per = 360 / speed;
          var who = {}; who[s0] = e.server; who[sideOf[e.receiver]] = e.receiver;
          var serveY = e.score_a % 2 === 0 ? 330 : 190;          // serve from the right or left court by the score
          piece(e.server, s0 ? 660 : 300, serveY, T.ti[P[e.server].team].c);
          piece(e.receiver, s0 ? 300 : 660, 520 - serveY, T.ti[P[e.receiver].team].c);
          if (!el.shuttle) return;
          el.shuttle.setAttribute('cx', s0 ? 640 : 320); el.shuttle.setAttribute('cy', serveY); el.shuttle.setAttribute('fill', '#fff');
          for (var h = 0; h < shots; h++) (function (h) {
            later(function () {
              var to = 1 - ((s0 + h) % 2), last = h === shots - 1;
              var tx = to ? 540 + rnd(e.rally * 31 + h + e.game) * 330 : 90 + rnd(e.rally * 17 + h + e.game) * 330;
              var ty = 115 + rnd(e.rally * 7 + h * 3 + e.game) * 290;
              if (last) tx = w === 0 ? 560 + rnd(e.rally) * 300 : 100 + rnd(e.rally) * 300;   // lands on the loser's side
              if (!el.shuttle) return;
              el.shuttle.setAttribute('cx', tx); el.shuttle.setAttribute('cy', ty);
              if (!last) piece(who[to], tx + (to ? 26 : -26), ty + 8);                         // the receiver runs to it
              else el.shuttle.setAttribute('fill', e.type === 'fault' ? '#ef4444' : '#ffd166');
            }, h * per);
          })(h);
          var sc = {}; m.teams.forEach(function (t) { sc[t.id] = T.ti[t.id].i === 0 ? e.score_a : e.score_b; });
          later(function () {
            H('Game ' + e.game, 'rally ' + e.rally, clean(P[e.winner].name) + ' wins rally ' + e.rally + (e.shot ? ' — ' + e.shot.replace(/-/g, ' ') : '') +
              (e.fault ? ' — fault: ' + e.fault.replace(/-/g, ' ') : '') + '  (' + e.score_a + '–' + e.score_b + ', ' + e.length + ' shots)', sc);
          }, (shots - 1) * per);
        } });
      }
      if (e.type === 'game_end') st.push({ ms: 1500, run: function () { banner('GAME ' + e.game + ' · ' + e.score_a + '–' + e.score_b + ' · ' + clean(P[e.winner].name).toUpperCase(), T.ti[P[e.winner].team].c); } });
    });
    return { setup: setup, steps: st };
  }

  // ================= KHO-KHO: seated chasers in the lane, defenders keep running, the active chaser tags =================
  function khokho(m, H) {
    var T = teamColours(m), P = pn(m), score = {};
    var turns = {}; m.events.forEach(function (e) { if (e.turn !== undefined) (turns[e.turn] = turns[e.turn] || []).push(e); });
    function setup() {
      svg.innerHTML = ''; el = {};
      m.teams.forEach(function (t) { score[t.id] = 0; });
      node('rect', { x: 40, y: 60, width: 880, height: 400, fill: '#a8794b', stroke: '#fff', 'stroke-width': 3 });
      node('line', { x1: 120, y1: 260, x2: 840, y2: 260, stroke: '#fff', 'stroke-width': 2 });
      [120, 840].forEach(function (x) { node('rect', { x: x - 6, y: 240, width: 12, height: 40, fill: '#3b2a1a' }); });
      for (var i = 0; i < 8; i++) node('rect', { x: 200 + i * 80 - 13, y: 247, width: 26, height: 26, fill: 'rgba(255,255,255,.25)' });
      var t = node('text', { x: 480, y: 50, 'text-anchor': 'middle', 'class': 'st-lbl' }); t.textContent = 'CENTRAL LANE · 8 SEATED CHASERS FACING ALTERNATE SIDES · POLES AT BOTH ENDS · positions illustrative';
      var o = node('text', { x: 935, y: 75, 'text-anchor': 'end', 'class': 'st-lbl' }); o.textContent = 'OUT';
    }
    var st = [];
    Object.keys(turns).map(Number).sort(function (a, b) { return a - b; }).forEach(function (tn) {
      var evs = turns[tn], sum = evs.filter(function (e) { return e.type === 'turn'; })[0]; if (!sum) return;
      var chasers = m.players.filter(function (p) { return p.team === sum.chasing; }).slice(0, 9);
      var defs = m.players.filter(function (p) { return p.team === sum.defending; });
      var outN = 0;
      st.push({ ms: 1300, run: function () {
        clearPieces(); outN = 0;
        chasers.forEach(function (p, i) { piece(p.id, i < 8 ? 200 + i * 80 : 90, i < 8 ? 260 + (i % 2 ? 4 : -4) : 200, T.ti[p.team].c, String(p.jersey || ''), 14); });
        defs.filter(function (p) { return p.batch === 1; }).forEach(function (p, i) { piece(p.id, 300 + i * 170, i % 2 ? 380 : 140, T.ti[p.team].c, String(p.jersey || ''), 14); });
        H('Turn ' + tn, T.ti[sum.chasing].t.short + ' chasing', 'Turn ' + tn + ': ' + clean(T.ti[sum.chasing].t.name) + ' chase, ' + clean(T.ti[sum.defending].t.name) + ' defend in batches of 3.', score);
        banner('TURN ' + tn + ' · ' + T.ti[sum.chasing].t.short + ' CHASE', T.ti[sum.chasing].c);
      } });
      evs.filter(function (e) { return e.type === 'tag'; }).forEach(function (g) {
        st.push({ ms: 1050, run: function () {
          Object.keys(el).forEach(function (pid, q) {   // defenders on the field keep running
            if (P[pid] && P[pid].team === sum.defending && alive(pid)) piece(pid, 150 + rnd(g.time + q * 7) * 660, 85 + rnd(g.time * 3 + q) * 350);
          });
          if (!alive(g.defender)) piece(g.defender, 150 + rnd(g.time + 99) * 660, 85 + rnd(g.time + 7) * 350, T.ti[sum.defending].c, String(P[g.defender].jersey || ''), 14);
          if (el[g.defender]) el[g.defender].classList.remove('dead');
          var d = posOf(g.defender), c0 = posOf(g.tagger);
          later(function () {
            piece(g.tagger, d[0] - 22, d[1], T.ti[sum.chasing].c, String(P[g.tagger].jersey || ''), 14);     // the active chaser runs in
            later(function () {
              flash(d[0] - 22, d[1], d[0], d[1], '#fff');
              piece(g.defender, 900, 95 + (outN++ % 10) * 36);                                                  // out: off the field
              if (el[g.defender]) el[g.defender].classList.add('dead');
              piece(g.tagger, c0[0], c0[1]);                                                                     // back to the lane
            }, 380 / speed);
          }, 300 / speed);
          score[sum.chasing] += g.points;
          H(null, g.time + 's', clean(P[g.tagger].name) + ' tags ' + clean(P[g.defender].name) + ' — ' + String(g.method).replace(/-/g, ' ') + ' (+' + g.points + ', batch ' + g.batch + ')', score);
        } });
      });
    });
    return { setup: setup, steps: st };
  }
  var BUILD = { valorant: valorant, badminton: badminton, khokho: khokho };

  // ---------- player ----------
  var model = null, built = null, scoreNow = {}, name = null;
  function hud(clock, sub, text, sc) {
    if (clock !== null && clock !== undefined) $('#stClock').textContent = clock;
    if (sub !== null && sub !== undefined) $('#stSub').textContent = sub;
    if (text) $('#stCom').textContent = text;
    if (sc) { scoreNow = {}; Object.keys(sc).forEach(function (k) { scoreNow[k] = sc[k]; }); }
    var T = teamColours(model);
    [$('#stA'), $('#stB')].forEach(function (box, i) {
      var t = T.order[i]; box.innerHTML = '<span class="sw" style="background:' + COL[i] + '"></span><span>' + esc(t.name) + '</span><b>' + (scoreNow[t.id] !== undefined ? scoreNow[t.id] : 0) + '</b>';
    });
  }
  function stop() { playing = false; clearTimeout(timer); $('#stPlay').textContent = '▶ Play'; }
  function tick() {
    if (!playing) return;
    if (idx >= steps.length) { stop(); hud(null, 'full time', 'Full time: ' + model.teams.map(function (t) { return clean(t.name) + ' ' + model.result.scores[t.id]; }).join(' – '), model.result.scores); return; }
    steps[idx].run(); idx++; $('#stScrub').value = idx; $('#stN').textContent = idx + ' / ' + steps.length;
    timer = setTimeout(tick, steps[idx - 1].ms / speed);
  }
  function load(n) {
    stop(); timers.forEach(clearTimeout); timers = []; name = n; model = API.rebuild(n); scoreNow = {};
    var sn = SP[n].snippets;
    if (sn) {
      ['json', 'turtle', 'jsonld'].forEach(function (k) { stageSec.querySelector('#stCode .tab-panel[data-p="' + k + '"] code').innerHTML = sn[k]; });
      $('#stNote').textContent = sn.note;
    }
    model.teams.forEach(function (t) { scoreNow[t.id] = 0; });
    built = BUILD[n](model, hud); steps = built.steps; idx = 0; built.setup();
    $('#stScrub').max = steps.length; $('#stScrub').value = 0; $('#stN').textContent = '0 / ' + steps.length;
    var d = API.diff(n);
    $('#stDiff').textContent = 'diff = ' + d.diffs + (d.diffs ? ' ✕' : ' ✓') + ' · from JSON-LD';
    $('#stEyebrow').textContent = SP[n].label + ' · live replay · simulated match';
    $('#stTitle').textContent = clean(model.match.name) + ' — replayed from Sport Schema data only';
    $('#stIntro').textContent = (model.match.competition ? clean(model.match.competition.name) + '. ' : '') + 'A simulated match (made-up teams and players). Every event on this ' +
      (n === 'valorant' ? 'map' : n === 'badminton' ? 'court' : 'field') + ' is read from the converted JSON-LD (' + model.events.length +
      ' events); the in-page check compares it with the original JSON field by field. Positions are illustrative.';
    hud('Ready', '', 'Press play.', scoreNow);
  }
  function seek(k) {
    var was = playing; stop();
    timers.forEach(clearTimeout); timers = [];
    built.setup(); scoreNow = {}; model.teams.forEach(function (t) { scoreNow[t.id] = 0; });
    var saved = speed; speed = 1000;
    for (idx = 0; idx < k; idx++) steps[idx].run();
    speed = saved;
    document.querySelectorAll('.st-flash,.st-banner').forEach(function (n) { n.remove(); });
    $('#stScrub').value = idx; $('#stN').textContent = idx + ' / ' + steps.length;
    if (was) { playing = true; $('#stPlay').textContent = '❚❚ Pause'; tick(); }
  }
  $('#stPlay').addEventListener('click', function () {
    if (playing) stop();
    else { if (idx >= steps.length) seek(0); playing = true; $('#stPlay').textContent = '❚❚ Pause'; tick(); }
  });
  $('#stRestart').addEventListener('click', function () { seek(0); });
  $('#stScrub').addEventListener('input', function () { seek(parseInt(this.value, 10)); });
  document.querySelectorAll('.st-speed button').forEach(function (b) {
    b.addEventListener('click', function () { speed = +b.dataset.sp; document.querySelectorAll('.st-speed button').forEach(function (x) { x.classList.toggle('on', x === b); }); });
  });

  function select(s) {
    document.querySelectorAll('.sport-bar button').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.s === s); });
    document.body.classList.toggle('mode-other', s !== 'kabaddi');
    if (s !== 'kabaddi') { load(s); API.show(s); window.scrollTo({ top: 0 }); }
    else { stop(); name = 'kabaddi'; }
  }
  bar.querySelectorAll('button').forEach(function (b) { b.addEventListener('click', function () { select(b.dataset.s); }); });
  window.RaidReplayStage = { select: select, play: function () { $('#stPlay').click(); }, state: function () { return { sport: name, idx: idx, steps: steps.length }; } };
})();
