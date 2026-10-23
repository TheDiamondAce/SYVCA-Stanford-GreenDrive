(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const PERIOD = 48, SAMPLE = .25, THRESHOLD = 60, RELEASE = 52;
  let elapsed = 0, running = true, mode = 'auto', restricted = false;
  let emissions = 28, displaySpeed = 20, lastFrame = 0, sampleClock = 0;
  let history = Array.from({length: 241}, (_, i) => 28 + 2 * Math.sin(i * .19) + Math.sin(i * .47));

  function autoValue(t) {
    const x = t % PERIOD;
    const base = x < 10 ? 28 : x < 19 ? 28 + (x - 10) / 9 * 58 : x < 28 ? 86 : x < 40 ? 86 - (x - 28) / 12 * 58 : 28;
    return base + 2.1 * Math.sin(t * 1.8) + 1.2 * Math.sin(t * 4.1);
  }
  function updateGate(value, previous) {
    return previous ? value > RELEASE : value >= THRESHOLD;
  }
  function drawChart() {
    const points = history.map((v, i) => [38 + i / 240 * 642, 180 - v * 1.6]);
    const path = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
    $('chartLine').setAttribute('d', path);
    $('chartArea').setAttribute('d', `${path} L680,180 L38,180Z`);
    $('chartDot').setAttribute('cx', 680);
    $('chartDot').setAttribute('cy', points[240][1]);
    $('chartDesc').textContent = `Simulated emissions index ${Math.round(emissions)} out of 100. Throttle engages at 60 and releases at 52. ${restricted ? 'Speed restricted to 8' : 'Speed limit 20'} kilometers per hour.`;
  }
  function render() {
    const rounded = Math.round(emissions);
    $('emissions').textContent = rounded;
    $('logicValue').textContent = rounded;
    $('operator').textContent = emissions >= THRESHOLD ? ' ≥ ' : ' < ';
    document.body.classList.toggle('restricted', restricted);
    $('airState').textContent = emissions >= THRESHOLD ? 'HIGH EMISSIONS' : restricted ? 'RECOVERING' : 'LOW EMISSIONS';
    $('decisionLabel').textContent = restricted ? 'Speed restriction active' : 'Threshold clear';
    $('decisionDetail').textContent = restricted ? 'Release when index falls to 52' : 'Normal speed envelope enabled';
    $('gatePill').textContent = restricted ? 'GATE LIMITED' : 'GATE OPEN';
    $('speedStatus').textContent = restricted ? 'CLIMATE SPEED LIMIT ACTIVE' : 'FULL SPEED AVAILABLE';
    $('speedNote').textContent = restricted ? 'High emissions → reduced speed envelope.' : 'Low emissions. Normal driving envelope.';
    $('throttle').textContent = restricted ? '40%' : '100%';
    $('throttleBar').style.width = restricted ? '40%' : '100%';
    const x = elapsed % PERIOD;
    $('timelineProgress').style.width = `${x / PERIOD * 100}%`;
    $('timecode').textContent = `00:${String(Math.floor(x)).padStart(2,'0')} / 00:48`;
    $('sceneTitle').textContent = mode === 'spike' ? 'Manual — Emissions spike' : mode === 'clear' ? 'Manual — Clearing the air' : x < 10 ? '01 — Clear conditions' : x < 19 ? '02 — Emissions rising' : x < 28 ? '03 — Speed reduced' : x < 40 ? '04 — Air clears, speed returns' : '05 — Normal speed restored';
    $('modeLabel').textContent = mode === 'auto' ? '48-SECOND AUTO LOOP' : 'MANUAL OVERRIDE';
    $('spike').classList.toggle('active', mode === 'spike');
    $('clear').classList.toggle('active', mode === 'clear');
    $('spike').setAttribute('aria-pressed', String(mode === 'spike'));
    $('clear').setAttribute('aria-pressed', String(mode === 'clear'));
    $('directorHint').textContent = mode === 'auto' ? 'A repeatable sequence for your pitch video. Press R to restart.' : 'Manual scene held for filming. Press R to return to the automatic loop.';
    drawChart();
  }
  function renderSpeed() {
    $('speed').textContent = Math.round(displaySpeed);
    $('gaugeArc').setAttribute('stroke-dasharray', `${displaySpeed / 20 * 100} 100`);
  }
  function sample() {
    if (mode === 'auto') emissions = autoValue(elapsed);
    else {
      const target = (mode === 'spike' ? 87 : 27) + 1.8 * Math.sin(elapsed * 2);
      emissions += Math.max(-3.5, Math.min(3.5, target - emissions));
    }
    emissions = Math.round(emissions);
    restricted = updateGate(emissions, restricted);
    history.push(emissions); history.shift();
    render();
  }
  function frame(time) {
    const dt = lastFrame ? Math.min((time - lastFrame) / 1000, .1) : 0;
    lastFrame = time;
    if (running) {
      elapsed += dt; sampleClock += dt;
      while (sampleClock >= SAMPLE) { sampleClock -= SAMPLE; sample(); }
      const target = restricted ? 8 : 20;
      displaySpeed += (target - displaySpeed) * (1 - Math.exp(-dt * 5));
      renderSpeed();
    }
    requestAnimationFrame(frame);
  }
  function setRunning(value) {
    running = value;
    $('playPause').textContent = running ? 'Ⅱ' : '▶';
    $('playPause').setAttribute('aria-label', running ? 'Pause simulation' : 'Play simulation');
    $('feedBadge').innerHTML = `<i></i> ${running ? 'LIVE DEMO' : 'PAUSED'}`;
  }
  function restart() {
    elapsed = 0; emissions = 28; restricted = false; displaySpeed = 20; sampleClock = 0; mode = 'auto';
    history = Array.from({length:241}, (_,i) => 28 + 2 * Math.sin(i * .19) + Math.sin(i * .47));
    setRunning(true); render(); renderSpeed();
  }
  function present(value) {
    document.body.classList.toggle('presenting', value);
    $('exitPresent').hidden = !value;
    if (value) window.scrollTo(0, 0);
    (value ? $('exitPresent') : $('present')).focus();
  }
  $('playPause').addEventListener('click', () => setRunning(!running));
  $('restart').addEventListener('click', restart);
  for (const choice of ['spike','clear']) $(choice).addEventListener('click', () => { mode = choice; setRunning(true); render(); });
  $('present').addEventListener('click', () => present(true));
  $('exitPresent').addEventListener('click', () => present(false));
  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || /INPUT|TEXTAREA|SELECT/.test(event.target.tagName)) return;
    if (event.code === 'Space' && event.target.tagName !== 'BUTTON' && event.target.tagName !== 'A') { event.preventDefault(); setRunning(!running); }
    if (event.key.toLowerCase() === 'r') restart();
    if (event.key === 'Escape' && document.body.classList.contains('presenting')) present(false);
  });
  render(); renderSpeed(); requestAnimationFrame(frame);
})();
