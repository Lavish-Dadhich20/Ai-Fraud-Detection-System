// ═══════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════
let API = 'http://localhost:8000';
let activeNavBtn = document.querySelector('.ntab.active');
let activeSI = document.querySelector('.si.active');
let selectedUser = null;
let allUsers = [];
let allRecipients = [];
let currentTxnCtx = null;
let otpTimer = null;
let generatedOtp = '';
let chartsBuilt = false;
let currentLogFilter = 'all';
let chartInstances = {};

const fmtINR = n => '₹' + parseFloat(n).toLocaleString('en-IN');
const rand = (a,b) => Math.floor(Math.random()*(b-a+1))+a;

// ═══════════════════════════════════════════════════════════
// API HELPERS  — all calls go through here
// ═══════════════════════════════════════════════════════════
async function api(path, opts={}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(10000),
    ...opts
  });
  if (!res.ok) {
    const err = await res.json().catch(()=>({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ═══════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════
function goto(name, navBtn, si) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');

  if (navBtn) {
    if (activeNavBtn) activeNavBtn.classList.remove('active');
    navBtn.classList.add('active'); activeNavBtn = navBtn;
    const map = { dashboard:0, detect:1, logs:2, analytics:3, about:4 };
    document.querySelectorAll('.si').forEach(s => s.classList.remove('active'));
    const sis = document.querySelectorAll('.si');
    if (map[name] !== undefined) { sis[map[name]].classList.add('active'); activeSI = sis[map[name]]; }
  }
  if (si) {
    if (activeSI) activeSI.classList.remove('active');
    si.classList.add('active'); activeSI = si;
    const tabs = document.querySelectorAll('.ntab');
    const map = { dashboard:0, detect:1, logs:2, analytics:3, about:4 };
    tabs.forEach(t => t.classList.remove('active'));
    if (map[name] !== undefined) { tabs[map[name]].classList.add('active'); activeNavBtn = tabs[map[name]]; }
  }

  if (name === 'logs') loadLogs();
  if (name === 'analytics') loadAnalytics();
}

// ═══════════════════════════════════════════════════════════
// DB CONNECTION CHECK
// ═══════════════════════════════════════════════════════════
async function checkDB() {
  const ind = document.getElementById('db-indicator');
  try {
    // Try /health first (fast), then /stats for DB confirmation
    await api('/health');
    await api('/stats');
    ind.textContent = '● MongoDB'; ind.className = 'db-status connected';
    return true;
  } catch {
    try {
      // If /stats fails but /health works, API is up but DB may be seeding
      await api('/health');
      ind.textContent = '● MongoDB'; ind.className = 'db-status disconnected';
    } catch {
      ind.textContent = '● MongoDB'; ind.className = 'db-status disconnected';
    }
    return false;
  }
}

// ═══════════════════════════════════════════════════════════
// SEED DATABASE
// ═══════════════════════════════════════════════════════════
async function seedDB() {
  const btn = document.getElementById('seed-btn-nav');
  btn.textContent = '⏳ Seeding…'; btn.disabled = true;
  showToast('Seeding MongoDB with 500 transactions…', 'info');
  try {
    const r = await api('/seed', { method: 'POST' });
    showToast(`✓ DB Seeded — ${r.transactions} txns, ${r.fraud_transactions} fraud`, 'ok');
    await loadDashboard();
    await loadUserCards();
  } catch(e) {
    showToast('Seed failed: ' + e.message, 'err');
  }
  btn.textContent = '⚙ Seed DB'; btn.disabled = false;
}

// ═══════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const [stats, txns] = await Promise.all([
      api('/stats'),
      api('/transactions?limit=8')
    ]);
    setDBConnected(true);
    // Stats
    animNum('d-total', stats.total);
    animNum('d-fraud', stats.fraud);
    animNum('d-safe', stats.safe);
    document.getElementById('d-latency').textContent = stats.avg_latency_ms + 'ms';
    document.getElementById('d-fraud-sub').textContent = 'Blocked this session';
    document.getElementById('d-total-sub').textContent = `${stats.safe} safe, ${stats.review} review`;
    document.getElementById('d-safe-sub').textContent = 'Verified transactions';

    // Sidebar
    document.getElementById('sb-fraud-val').textContent = stats.fraud;
    document.getElementById('sb-badge').textContent = stats.fraud + stats.review;
    const amountBlocked = txns.transactions
      .filter(t=>t.status==='FRAUD')
      .reduce((a,t)=>a+t.transaction_amount,0);
    document.getElementById('sb-fraud-sub').textContent = amountBlocked > 0
      ? '₹' + Math.round(amountBlocked/1000) + 'K blocked' : 'From MongoDB';

    // Live table
    const tbody = document.getElementById('live-table');
    tbody.innerHTML = txns.transactions.slice(0,8).map(t => {
      const rc = t.status==='FRAUD'?'tr': t.status==='REVIEW'?'ta':'tc';
      const risk = Math.round((t.fraud_probability||0)*100);
      return `<tr>
        <td class="bright">${t.transaction_id}</td>
        <td class="bright">${fmtINR(t.transaction_amount)}</td>
        <td>${t.current_txn_location||'—'}</td>
        <td class="${rc}">${risk}%</td>
        <td><span class="badge ${t.status.toLowerCase()}">${t.status}</span></td>
      </tr>`;
    }).join('');
  } catch(e) {
    setDBConnected(false);
    showToast('DB not connected — run: uvicorn api_v2:app --host 0.0.0.0 --port 8000 --reload', 'err');
  }
}

function setDBConnected(ok) {
  const ind = document.getElementById('db-indicator');
  ind.textContent = ok ? '● MongoDB' : '● MongoDB';
  ind.className = 'db-status ' + (ok ? 'connected' : 'disconnected');
}

// ═══════════════════════════════════════════════════════════
// USER CARDS — loaded from MongoDB
// ═══════════════════════════════════════════════════════════
async function loadUserCards() {
  try {
    const data = await api('/users');
    allUsers = data.users;
    renderUserCards();
    if (allUsers.length > 0 && !selectedUser) {
      selectedUser = allUsers[0];
      updateSenderInfo();
    }
  } catch {
    // Fallback static users
    allUsers = [
      {_id:'user_001',name:'Rahul Sharma',bank:'HDFC Bank',avg_txn_amount:2000,usual_location:'Udaipur',known_devices:['device_abc123'],phone:'98XX-XXXX-12',email:'rahul.s@email.com',pan:'ABCPS1234R',aadhaar:'XXXX-XXXX-1234',address:'12 Lake View Colony, Udaipur, Rajasthan 313001',branch:'Udaipur Main',ifsc:'HDFC0001234',account:'XXXX XXXX 4321'},
      {_id:'user_002',name:'Priya Mehta',bank:'ICICI Bank',avg_txn_amount:8000,usual_location:'Mumbai',known_devices:['device_def456'],phone:'91XX-XXXX-56',email:'priya.m@email.com',pan:'CDEFS5678K',aadhaar:'XXXX-XXXX-5678',address:'45 Sea View Apartments, Mumbai, Maharashtra 400050',branch:'Bandra West',ifsc:'ICICI0005678',account:'XXXX XXXX 8765'},
      {_id:'user_003',name:'Arjun Patel',bank:'SBI',avg_txn_amount:1200,usual_location:'Ahmedabad',known_devices:['device_ghi789'],phone:'79XX-XXXX-90',email:'arjun.p@email.com',pan:'GHIJK9012P',aadhaar:'XXXX-XXXX-9012',address:'7 Commerce House, Ahmedabad, Gujarat 380009',branch:'Navrangpura',ifsc:'SBIN0009012',account:'XXXX XXXX 2109'},
    ];
    renderUserCards();
    if (!selectedUser) { selectedUser = allUsers[0]; updateSenderInfo(); }
  }
}

function renderUserCards() {
  const wrap = document.getElementById('user-cards');
  if (!wrap) return;
  wrap.innerHTML = allUsers.map(u => `
    <div onclick="selectUser('${u._id}')" style="background:var(--card);border:1px solid ${u._id===selectedUser?._id?'rgba(0,245,212,.3)':'var(--b)'};border-radius:var(--r);padding:11px;cursor:pointer;transition:all .15s;">
      <div style="font-family:var(--mono);font-size:14px;letter-spacing:1.5px;color:${u._id===selectedUser?._id?'var(--teal)':'var(--ts)'};text-transform:uppercase;margin-bottom:3px;">${u._id}</div>
      <div style="font-size:18px;font-weight:600;color:#000000;margin-bottom:2px;">${u.name}</div>
      <div style="font-size:15px;color:var(--ts);">Avg: ${fmtINR(u.avg_txn_amount)} · ${u.usual_location}</div>
      <div style="font-size:14px;color:var(--ts);margin-top:2px;">${u.bank||'Bank'}</div>
    </div>`).join('');
}

function selectUser(id) {
  selectedUser = allUsers.find(u => u._id === id) || allUsers[0];
  renderUserCards();
  updateSenderInfo();
}

function updateSenderInfo() {
  const el = document.getElementById('sender-info');
  if (!el || !selectedUser) return;
  el.innerHTML = `<span style="color:var(--tp);">${selectedUser.name}</span> &nbsp;·&nbsp; Avg: <span style="color:var(--blue);font-family:var(--mono);">${fmtINR(selectedUser.avg_txn_amount)}</span> &nbsp;·&nbsp; Usual: <span style="color:var(--blue);">${selectedUser.usual_location}</span> &nbsp;·&nbsp; Device: <span style="color:var(--ts);">${selectedUser.known_devices?.[0]||'—'}</span>`;
}

// ═══════════════════════════════════════════════════════════
// DETECT  — calls FastAPI → XGBoost → saves to MongoDB
// ═══════════════════════════════════════════════════════════
async function runDetect() {
  const amount = parseFloat(document.getElementById('f-amount').value);
  const currLoc = document.getElementById('f-curr-loc').value.trim();
  const hour = parseInt(document.getElementById('f-hour').value) || new Date().getHours();
  const deviceVal = document.getElementById('f-device').value;
  const v15 = parseInt(document.getElementById('f-v15').value) || 0;
  const recipientId = document.getElementById('f-recipient').value;

  if (!amount || !currLoc) { showToast('Fill Amount and Current Location', 'err'); return; }
  if (!selectedUser) { showToast('Select a user first', 'err'); return; }

  const recipData = { 'SBI0001':{avg:2000,count:450}, 'SBI0002':{avg:300,count:4}, 'HDFC001':{avg:15000,count:1200} };
  const recip = recipData[recipientId] || recipData['SBI0001'];
  const deviceId = deviceVal === 'known' ? (selectedUser.known_devices?.[0] || 'device_known') : 'device_unknown_'+rand(1000,9999);

  const btn = document.getElementById('detect-btn');
  btn.disabled = true; btn.textContent = 'ANALYZING…';

  const STEPS = [
    'Fetching sender profile from MongoDB…',
    'Resolving geo-coordinates via OpenCage API…',
    'Calculating Haversine distance…',
    'Running XGBoost inference…',
    'Saving result to MongoDB…',
  ];
  let si = 0;
  document.getElementById('result-area').innerHTML = `<div class="spinner-wrap"><div class="spinner"></div><div class="spin-steps" id="spin-step">${STEPS[0]}</div></div>`;
  document.getElementById('xai-area').innerHTML = '<div style="font-family:var(--mono);font-size:14px;color:var(--tm);">// Processing…</div>';
  document.getElementById('result-latency').textContent = '';

  const spinTimer = setInterval(() => {
    si = (si+1) % STEPS.length;
    const el = document.getElementById('spin-step');
    if (el) el.textContent = STEPS[si];
  }, 650);

  const params = new URLSearchParams({
    user_id: selectedUser._id,
    transaction_amount: amount,
    transaction_hour: hour,
    current_txn_location: currLoc,
    device_id: deviceId,
    transactions_last_15min: v15,
    recipient_avg_inflow: recip.avg,
    recipient_txn_history_count: recip.count,
  });

  const t0 = performance.now();
  let result = null;

  try {
    result = await api(`/predict?${params}`, { method: 'POST' });
    document.getElementById('api-sl').className = 'api-sl ok';
    document.getElementById('api-sl').textContent = '// ✓ Model responded · Result saved to MongoDB';
  } catch(e) {
    // Smart offline simulation
    result = simulateOffline({ amount, currLoc, hour, deviceVal, v15, recip, selectedUser });
    document.getElementById('api-sl').className = 'api-sl info';
    document.getElementById('api-sl').textContent = '// Demo mode — API not connected: ' + e.message;
  }

  clearInterval(spinTimer);
  const latency = Math.round(performance.now() - t0);
  btn.disabled = false; btn.textContent = '▶ ANALYZE TRANSACTION';

  currentTxnCtx = { result, payload: { amount, currLoc, hour, deviceVal, v15, recipientId, selectedUser: {...selectedUser} } };
  renderResult(result, latency);

  const status = result.status || (result.label===1 ? 'FRAUD' : result.fraud_probability>0.4 ? 'REVIEW' : 'SAFE');
  if (status === 'FRAUD' || status === 'REVIEW') {
    setTimeout(() => showBankAlert(), 900);
  }

  // Reload dashboard stats
  loadDashboard().catch(()=>{});
}

// ── OFFLINE SIMULATION (mirrors predict.py + _suspicion_score logic exactly) ─
// Uses the same 7 features as the real XGBoost model:
//   transaction_amount, transaction_hour, device_id_match,
//   sender_avg_txn_amount, location_deviation_km,
//   amount_deviation_ratio, transactions_last_15min
function simulateOffline({ amount, currLoc, hour, deviceVal, v15, recip, selectedUser }) {
  // Geo lookup table matching geo_lookup.py LOCATION_DB
  const coords = {
    'udaipur':[24.5854,73.7125],'mumbai':[19.0760,72.8777],'delhi':[28.6139,77.2090],
    'new delhi':[28.6139,77.2090],'jaipur':[26.9124,75.7873],'bangalore':[12.9716,77.5946],
    'bengaluru':[12.9716,77.5946],'hyderabad':[17.3850,78.4867],'chennai':[13.0827,80.2707],
    'kolkata':[22.5726,88.3639],'pune':[18.5204,73.8567],'ahmedabad':[23.0225,72.5714],
    'indore':[22.7196,75.8577],'lucknow':[26.8467,80.9462],'noida':[28.5355,77.3910],
    'jodhpur':[26.2389,73.0243],'kota':[25.2138,75.8648],'surat':[21.1702,72.8311],
    'chandigarh':[30.7333,76.7794],'nagpur':[21.1458,79.0882],'bhopal':[23.2599,77.4126],
    'agra':[27.1767,78.0081],'varanasi':[25.3176,82.9739],'amritsar':[31.6340,74.8723],
    'rajasthan':[27.0238,74.2179],'kerala':[10.8505,76.2711],'gujarat':[22.2587,71.1924],
    'maharashtra':[19.7515,75.7139],'karnataka':[15.3173,75.7139],'punjab':[31.1471,75.3412],
    'new york':[40.7128,-74.0060],'london':[51.5074,-0.1278],'dubai':[25.2048,55.2708],
    'singapore':[1.3521,103.8198],'bangkok':[13.7563,100.5018],
  };
  function hav(la1, lo1, la2, lo2) {
    const R = 6371, d = n => n * Math.PI / 180;
    const a = Math.sin(d(la2-la1)/2)**2 + Math.cos(d(la1))*Math.cos(d(la2))*Math.sin(d(lo2-lo1)/2)**2;
    return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
  }

  // Resolve usual location — use stored lat/lon from MongoDB user if available
  let usual;
  if (selectedUser.usual_lat && selectedUser.usual_lon) {
    usual = [selectedUser.usual_lat, selectedUser.usual_lon];
  } else {
    usual = coords[(selectedUser.usual_location||'udaipur').toLowerCase()] || [26.9124, 75.7873];
  }
  const curr = coords[currLoc.toLowerCase()] || null;
  const dist = curr ? hav(usual[0], usual[1], curr[0], curr[1]) : rand(50, 600);

  const avg  = selectedUser.avg_txn_amount || 2000;
  const amtR = amount / Math.max(avg, 1);
  const newDevice = deviceVal === 'unknown' ? 1 : 0;

  // Mirror _suspicion_score() from data_generator.py (max 155 points → 0-1)
  let score = 0;
  // Amount deviation (0-45)
  if      (amtR >= 20) score += 45;
  else if (amtR >= 15) score += 36;
  else if (amtR >= 10) score += 27;
  else if (amtR >= 5)  score += 16;
  else if (amtR >= 3)  score += 7;
  // Location (0-25)
  if      (dist >= 5000) score += 25;
  else if (dist >= 2000) score += 20;
  else if (dist >= 1000) score += 15;
  else if (dist >= 500)  score += 10;
  else if (dist >= 200)  score += 5;
  else if (dist >= 50)   score += 2;
  // New device (0-25)
  if (newDevice) score += 25;
  // Night hour (0-10)
  if      (hour >= 0 && hour <= 2) score += 10;
  else if (hour >= 3 && hour <= 5) score += 7;
  // Velocity (0-50)
  if      (v15 >= 12) score += 50;
  else if (v15 >= 8)  score += 40;
  else if (v15 >= 5)  score += 28;
  else if (v15 >= 3)  score += 13;
  else if (v15 >= 2)  score += 5;

  let s = Math.min(0.99, Math.max(0.01, score / 155 + (Math.random() * 0.06 - 0.03)));

  const label  = s >= 0.5 ? 1 : 0;
  const status = s >= 0.5 ? 'FRAUD' : s > 0.4 ? 'REVIEW' : 'SAFE';
  const conf   = s >= 0.8 || s <= 0.2 ? 'HIGH' : s >= 0.6 || s <= 0.4 ? 'MEDIUM' : 'LOW — borderline, recommend manual review';

  // Build risk factors matching predict.py _build_risk_factors()
  const rf = [];
  if (amtR >= 5)  rf.push(`Amount spike: ${amtR.toFixed(1)}x avg — ${amtR>=20?'VERY HIGH spike (20x+)':amtR>=15?'HIGH spike (15–20x)':amtR>=10?'moderate spike (10–15x)':'mild spike (5–10x)'}`);
  if (newDevice)  rf.push('Unknown / new device — not sender\'s registered device');
  if (dist > 50)  rf.push(`Location: ${dist} km from usual — ${dist>=2000?'VERY HIGH (likely outside India)':dist>=500?'HIGH (far region of India)':dist>=200?'moderate (different city/state)':'mild deviation'}`);
  if (v15 >= 2)   rf.push(`Velocity: ${v15} transactions in last 15 min — ${v15>=7?'ACCOUNT DRAIN pattern':v15>=4?'suspicious velocity':'slightly elevated'}`);
  if (hour >= 0 && hour <= 5) rf.push(`Unusual hour: ${String(hour).padStart(2,'0')}:00 (late night / early morning)`);
  if (!rf.length) rf.push('No significant risk factors detected');

  const currName = curr ? currLoc : currLoc + ' (coords estimated)';
  return {
    prediction: label ? 'Fraud' : 'Not Fraud', label, status,
    fraud_probability: Math.round(s * 10000) / 10000,
    confidence: conf, threshold_used: 0.5, risk_factors: rf,
    amount_deviation_ratio: Math.round(amtR * 100) / 100,
    location_deviation_km: dist,
    usual_location: selectedUser.usual_location,
    current_location: currName,
    transaction_id: 'TXN_' + Math.random().toString(36).substr(2, 8).toUpperCase(),
    latency_ms: rand(18, 46),
  };
}

// ── RENDER RESULT ────────────────────────────────────────────────────────
function renderResult(r, latency) {
  const score = Math.round((r.fraud_probability||0)*100);
  const status = r.status || (r.label===1?'FRAUD': r.fraud_probability>0.4?'REVIEW':'SAFE');
  const clr = status==='FRAUD'?'var(--red)':status==='REVIEW'?'var(--orange)':'var(--green)';
  const barClr = status==='FRAUD'?'#ff3b30':status==='REVIEW'?'#ff9500':'#34c759';
  const icon = status==='FRAUD'?'🚨':status==='REVIEW'?'⚠':'✅';
  const lbl = status==='FRAUD'?'FRAUD DETECTED':status==='REVIEW'?'FLAGGED FOR REVIEW':'TRANSACTION SAFE';

  document.getElementById('result-latency').textContent = (r.latency_ms||latency)+'ms';
  document.getElementById('result-area').innerHTML = `
    <div>
      <div style="font-family:var(--mono);font-size:14px;letter-spacing:2px;color:${clr};margin-bottom:5px;">${icon} ${lbl}</div>
      <div style="font-family:var(--mono);font-size:45px;font-weight:700;color:${clr};text-shadow:none;margin-bottom:4px;">${score}%</div>
      <div style="font-size:17px;color:var(--ts);">Risk Score · ${r.confidence} confidence</div>
      <div class="score-bar-wrap"><div class="score-bar-fill" id="r-bar" style="width:0%;background:${barClr};box-shadow:0 0 10px ${barClr}44;"></div></div>
      <div class="score-bar-labels"><span>0% SAFE</span><span>50% THRESHOLD</span><span>100% FRAUD</span></div>
      <div class="result-meta">
        <div class="rmeta"><div class="rmeta-label">TXN ID</div><div class="rmeta-val" style="font-size:14px;">${r.transaction_id||'—'}</div></div>
        <div class="rmeta"><div class="rmeta-label">Distance</div><div class="rmeta-val" style="color:${clr};">${r.location_deviation_km||0} km</div></div>
        <div class="rmeta"><div class="rmeta-label">Amt Dev</div><div class="rmeta-val" style="color:${clr};">${r.amount_deviation_ratio||'—'}x</div></div>
      </div>
      <div style="margin-top:10px;padding:9px;background:var(--card);border:1px solid var(--b);border-radius:var(--r);font-size:16px;color:var(--ts);">
        📍 ${r.usual_location||'—'} → ${r.current_location||r.current_txn_location||'—'}
      </div>
    </div>`;
  setTimeout(() => { const b = document.getElementById('r-bar'); if(b) b.style.width = score+'%'; }, 80);

  // XAI
  const reasons = r.risk_factors || [];
  document.getElementById('xai-area').innerHTML = `
    <div style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--ts);text-transform:uppercase;margin-bottom:10px;">Why this result?</div>
    <div class="xai-factors">${reasons.map(rf => {
      const isRed = /high|fraud|drain|unusual|unknown/i.test(rf);
      const isAmber = /moderate|mild|suspicious/i.test(rf);
      const dc = isRed?'var(--red)':isAmber?'var(--orange)':'var(--teal)';
      const parts = rf.split(':');
      return `<div class="xai-factor"><div class="xai-dot" style="background:${dc};box-shadow:0 0 5px ${dc}44;"></div><div><div class="xai-name">${parts[0]||rf}</div><div class="xai-desc">${parts.slice(1).join(':').trim()||rf}</div></div></div>`;
    }).join('')}</div>`;

  showToast(status==='FRAUD'?'🚨 Fraud Detected':status==='REVIEW'?'⚠ Flagged for Review':'✅ Transaction Safe', status==='FRAUD'?'err':status==='REVIEW'?'info':'ok');
}

// ═══════════════════════════════════════════════════════════
// LOGS — from MongoDB
// ═══════════════════════════════════════════════════════════
async function loadLogs() {
  const tbody = document.getElementById('log-table');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--tm);">Loading from MongoDB…</td></tr>';
  try {
    const filter = currentLogFilter === 'all' ? '' : `&status=${currentLogFilter}`;
    const data = await api(`/transactions?limit=200${filter}`);
    document.getElementById('log-count-tag').textContent = data.count + ' RECORDS';
    // Store transactions for modal lookup
    window._logTransactions = data.transactions;
    tbody.innerHTML = data.transactions.map((t, idx) => {
      const rc = t.status==='FRAUD'?'tr': t.status==='REVIEW'?'ta':'tc';
      const risk = Math.round((t.fraud_probability||0)*100);
      const reason = t.risk_factors?.[0] || '—';
      const linkClass = t.status==='FRAUD'?'red-link':t.status==='REVIEW'?'amber-link':'';
      return `<tr>
        <td class="bright">${t.transaction_id}</td>
        <td>${t.timestamp ? new Date(t.timestamp).toLocaleString('en-IN',{dateStyle:'short',timeStyle:'short'}) : '—'}</td>
        <td class="bright">${fmtINR(t.transaction_amount)}</td>
        <td>${t.user_name||t.user_id}</td>
        <td class="${rc}">${t.usual_location||'—'}</td>
        <td class="${rc}">${t.current_txn_location||'—'}</td>
        <td class="${rc}">${t.location_deviation_km||0} km</td>
        <td class="${rc}">${risk}%</td>
        <td><span class="badge ${t.status.toLowerCase()}">${t.status}</span></td>
        <td style="max-width:160px;">
          <span class="flag-reason-link ${linkClass}" title="Click to view full transaction details" onclick="openTxnDetail(${idx})">${reason}</span>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--tm);">No records</td></tr>';
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--red);">Cannot connect to MongoDB — ${e.message}</td></tr>`;
  }
}

function filterLog(f, btn) {
  currentLogFilter = f;
  document.querySelectorAll('.flt-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadLogs();
}

// ═══════════════════════════════════════════════════════════
// ANALYTICS — computed from MongoDB data
// ═══════════════════════════════════════════════════════════
async function loadAnalytics() {
  try {
    const [stats, txns] = await Promise.all([
      api('/stats'),
      api('/transactions?limit=500')
    ]);

    document.getElementById('an-total').textContent = stats.total;
    document.getElementById('an-fraud').textContent = stats.fraud;
    document.getElementById('an-safe').textContent = stats.safe;
    document.getElementById('an-latency').textContent = stats.avg_latency_ms + 'ms';

    buildCharts(txns.transactions);
  } catch {
    // Build charts with fallback data
    buildCharts(null);
  }
}

function buildCharts(txns) {
  // Destroy existing
  Object.values(chartInstances).forEach(c => c.destroy());
  chartInstances = {};

  const GRID = {color:'rgba(0,0,0,0.06)', borderColor:'rgba(0,0,0,0.06)'};
  const TICK = {color:'rgba(138,164,200,0.5)', font:{family:'JetBrains Mono', size:9}};
  const base = {responsive:true, maintainAspectRatio:false, animation:{duration:900},
    plugins:{legend:{display:false}},
    scales:{x:{grid:GRID,ticks:TICK,border:GRID}, y:{grid:GRID,ticks:TICK,border:GRID}}};

  // Build day buckets from real data
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const fraudByDay = [0,0,0,0,0,0,0];
  const safeByDay = [0,0,0,0,0,0,0];
  const hourBuckets = new Array(24).fill(0);
  const typeCount = {credential_theft:0, money_mule:0, velocity_attack:0, location_anomaly:0, other:0};

  if (txns && txns.length > 0) {
    txns.forEach(t => {
      const d = new Date(t.timestamp);
      const dow = (d.getDay()+6)%7;
      if (t.status==='FRAUD') fraudByDay[dow]++;
      else safeByDay[dow]++;
      hourBuckets[t.transaction_hour||0]++;
      if (t.status==='FRAUD') {
        const rf = (t.risk_factors||[]).join(' ').toLowerCase();
        if (rf.includes('drain') || rf.includes('velocity')) typeCount.velocity_attack++;
        else if (rf.includes('mule') || rf.includes('thin')) typeCount.money_mule++;
        else if (rf.includes('unknown device') || rf.includes('device')) typeCount.credential_theft++;
        else if (rf.includes('location') || rf.includes('km')) typeCount.location_anomaly++;
        else typeCount.other++;
      }
    });
  } else {
    // Fallback
    [38,52,44,61,47,55,47].forEach((v,i)=>fraudByDay[i]=v);
    [220,245,231,268,249,261,249].forEach((v,i)=>safeByDay[i]=v);
    [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23].forEach((h)=>{
      hourBuckets[h] = (h>=0&&h<=5)?rand(12,28):(h>=22)?rand(8,18):rand(1,10);
    });
    typeCount.location_anomaly=38; typeCount.credential_theft=24; typeCount.velocity_attack=18;
    typeCount.money_mule=12; typeCount.other=8;
  }

  chartInstances.trend = new Chart(document.getElementById('trendChart'), {type:'line',
    data:{labels:days, datasets:[
      {label:'Fraud',data:fraudByDay,borderColor:'#ff3b30',backgroundColor:'rgba(255,59,48,0.08)',fill:true,tension:.4,pointBackgroundColor:'#ff3b30',pointRadius:4},
      {label:'Safe/10',data:safeByDay.map(v=>Math.round(v/10)),borderColor:'rgba(0,122,255,0.45)',backgroundColor:'rgba(0,122,255,0.05)',fill:true,tension:.4,pointRadius:2}
    ]},
    options:{...base, plugins:{legend:{display:true,labels:{color:'rgba(80,80,95,0.7)',font:{family:'JetBrains Mono',size:9},boxWidth:8,padding:10}}}}
  });

  chartInstances.type = new Chart(document.getElementById('typeChart'), {type:'doughnut',
    data:{
      labels:['Location Spoof','Credential Theft','Velocity Attack','Money Mule','Other'],
      datasets:[{data:[typeCount.location_anomaly,typeCount.credential_theft,typeCount.velocity_attack,typeCount.money_mule,typeCount.other],
        backgroundColor:['#ff3b30','#ff9500','#007aff','#34c759','rgba(50,173,230,0.5)'],
        borderColor:'#03070f',borderWidth:3}]
    },
    options:{responsive:true,maintainAspectRatio:false,animation:{duration:900},
      plugins:{legend:{position:'right',labels:{color:'rgba(80,80,95,0.7)',font:{family:'JetBrains Mono',size:9},padding:8,boxWidth:10}}}}
  });

  // Scatter from real data
  const scatterFraud = [], scatterSafe = [];
  if (txns) {
    txns.slice(0, 150).forEach(t => {
      const pt = {x: t.transaction_amount, y: Math.round((t.fraud_probability||0)*100)};
      if (t.status==='FRAUD') scatterFraud.push(pt); else scatterSafe.push(pt);
    });
  } else {
    for(let i=0;i<50;i++){const f=Math.random()<.25;(f?scatterFraud:scatterSafe).push({x:rand(1000,500000),y:f?rand(60,99):rand(3,45)});}
  }
  chartInstances.scatter = new Chart(document.getElementById('scatterChart'), {type:'scatter',
    data:{datasets:[
      {label:'Fraudulent',data:scatterFraud,backgroundColor:'rgba(255,59,48,0.65)',pointRadius:5},
      {label:'Legitimate',data:scatterSafe,backgroundColor:'rgba(0,122,255,0.35)',pointRadius:4}
    ]},
    options:{...base,
      plugins:{legend:{display:true,labels:{color:'rgba(80,80,95,0.7)',font:{family:'JetBrains Mono',size:9},boxWidth:8}}},
      scales:{x:{...base.scales.x,title:{display:true,text:'Amount (₹)',color:'rgba(80,80,95,0.7)',font:{family:'JetBrains Mono',size:9}}},
              y:{...base.scales.y,title:{display:true,text:'Risk Score',color:'rgba(80,80,95,0.7)',font:{family:'JetBrains Mono',size:9}}}}}
  });

  chartInstances.hour = new Chart(document.getElementById('hourChart'), {type:'bar',
    data:{labels:Array.from({length:24},(_,h)=>h+':00'), datasets:[{
      data:hourBuckets,
      backgroundColor:hourBuckets.map(v=>v>18?'rgba(255,59,48,0.65)':v>8?'rgba(255,149,0,0.5)':'rgba(0,122,255,0.3)'),
      borderWidth:0,borderRadius:2
    }]},
    options:base
  });
}

// ═══════════════════════════════════════════════════════════
// BANK ALERT PHONE MODAL
// ═══════════════════════════════════════════════════════════
function showBankAlert() {
  if (!currentTxnCtx) return;
  const { result, payload } = currentTxnCtx;
  const user = payload.selectedUser;
  generatedOtp = String(Math.floor(100000 + Math.random()*900000));
  const score = Math.round((result.fraud_probability||0)*100);
  const now = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'});

  document.body.insertAdjacentHTML('beforeend', `
  <div class="overlay-bg" id="alert-overlay">
    <div class="phone-wrap">
      <div class="phone-label">📱 BANK ALERT — ${user.phone||'XXXX-XXXX-XX'}</div>
      <div class="phone">
        <div class="phone-notch"><div class="phone-notch-cut"></div></div>
        <div class="phone-status"><span class="phone-time">${now}</span><span class="phone-icons">▮▮▮ ● WiFi</span></div>
        <div class="phone-screen">
          <div class="bank-notif">
            <div class="bank-notif-hdr">
              <div class="bank-logo">🏦</div>
              <div><div class="bank-from-name">${user.bank||'HDFC Bank'}</div><div class="bank-from-sub">Fraud Alert System</div></div>
              <div class="bank-notif-time">Just now</div>
            </div>
            <div class="alert-pill">⚠ SUSPICIOUS TRANSACTION</div>
            <div class="alert-body-txt">
              Amount: <strong>${fmtINR(payload.amount)}</strong><br/>
              From: <strong>${user.usual_location}</strong> → <strong>${payload.currLoc}</strong><br/>
              Distance: <strong>${result.location_deviation_km||0} km</strong> · Risk: <strong style="color:#ff3355;">${score}%</strong>
            </div>
            <div class="alert-question">Was this YOU?</div>
            <div class="phone-btns">
              <button class="phone-btn yes" onclick="userSaysYes()">✅ YES, ME</button>
              <button class="phone-btn no" onclick="userSaysNo()">🚫 NOT ME!</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>`);
}

function userSaysYes() {
  const screen = document.querySelector('#alert-overlay .phone-screen');
  screen.innerHTML = `
    <div class="bank-notif">
      <div class="bank-notif-hdr"><div class="bank-logo">🏦</div><div><div class="bank-from-name">${currentTxnCtx?.payload?.selectedUser?.bank||'Bank'}</div><div class="bank-from-sub">OTP Verification</div></div></div>
      <div class="otp-demo-box">Demo OTP: <strong>${generatedOtp}</strong></div>
      <div class="otp-label">Enter 6-digit OTP</div>
      <div class="otp-boxes">${[0,1,2,3,4,5].map(i=>`<input class="otp-box" id="ob${i}" maxlength="1" oninput="otpNext(this,${i})"/>`).join('')}</div>
      <button class="otp-verify-btn" onclick="verifyOtp()">VERIFY &amp; APPROVE</button>
      <div class="otp-timer" id="otp-timer">Expires in 02:00</div>
    </div>`;
  startOtpTimer();
  setTimeout(() => document.getElementById('ob0')?.focus(), 80);
}

function otpNext(el, i) {
  el.value = el.value.replace(/\D/, '');
  if (el.value && i < 5) document.getElementById('ob'+(i+1))?.focus();
}

function startOtpTimer() {
  let s = 120;
  clearInterval(otpTimer);
  otpTimer = setInterval(() => {
    s--;
    const el = document.getElementById('otp-timer');
    if (el) { const m=String(Math.floor(s/60)).padStart(2,'0'),sc=String(s%60).padStart(2,'0'); el.textContent=`Expires in ${m}:${sc}`; if(s<=0){clearInterval(otpTimer);el.textContent='OTP expired';} }
    else clearInterval(otpTimer);
  }, 1000);
}

function verifyOtp() {
  const entered = [0,1,2,3,4,5].map(i => document.getElementById('ob'+i)?.value||'').join('');
  if (entered === generatedOtp) {
    clearInterval(otpTimer);
    const ctx = currentTxnCtx;
    const r = ctx.result;
    // Save response to MongoDB — also updates status to SAFE in the backend
    if (r.transaction_id) {
      api(`/transactions/${r.transaction_id}/respond`, {
        method:'POST', body:JSON.stringify({transaction_id:r.transaction_id, user_response:'yes_its_me', status:'approved'})
      }).then(() => {
        // Refresh dashboard + logs so they show SAFE instead of FRAUD
        loadDashboard().catch(()=>{});
      }).catch(()=>{});
    }
    // Update local result so any re-render also shows SAFE
    currentTxnCtx.result.status = 'SAFE';
    currentTxnCtx.result.label  = 0;
    const screen = document.querySelector('#alert-overlay .phone-screen');
    screen.innerHTML = `
      <div class="approved-screen">
        <span class="approved-icon">✅</span>
        <div class="approved-title">APPROVED</div>
        <p style="font-size:16px;color:rgba(255,255,255,.5);margin-bottom:12px;">Identity verified. Transaction processed.</p>
        <div class="approved-detail">
          <div class="arow"><span class="arow-label">Amount</span><span class="arow-val">${fmtINR(ctx.payload.amount)}</span></div>
          <div class="arow"><span class="arow-label">TXN ID</span><span class="arow-val">${r.transaction_id}</span></div>
          <div class="arow"><span class="arow-label">Status</span><span class="arow-val" style="color:var(--green);">✅ SAFE — Verified by user</span></div>
          <div class="arow"><span class="arow-label">MongoDB</span><span class="arow-val" style="color:var(--green);">Updated → SAFE ✓</span></div>
        </div>
        <button class="close-phone-btn" onclick="closeAlert()">Close</button>
      </div>`;
    showToast('✅ Transaction verified as SAFE — MongoDB updated', 'ok');
  } else {
    document.querySelectorAll('.otp-box').forEach(b=>{b.style.borderColor='rgba(255,51,85,.6)';});
    showToast('Incorrect OTP', 'err');
  }
}

function userSaysNo() {
  clearInterval(otpTimer);
  const caseNo = 'CYB-'+new Date().getFullYear()+'-'+String(rand(10000,99999));
  // Save to MongoDB as not_me
  if (currentTxnCtx?.result?.transaction_id) {
    api(`/transactions/${currentTxnCtx.result.transaction_id}/respond`, {
      method:'POST', body:JSON.stringify({transaction_id:currentTxnCtx.result.transaction_id, user_response:'not_me', status:'blocked_police'})
    }).catch(()=>{});
  }
  currentTxnCtx._caseNo = caseNo;
  // Send fraud alert emails via Resend
  sendFraudEmails(caseNo);
  closeAlert();
  setTimeout(() => showPoliceReport(), 320);
}

// ═══════════════════════════════════════════════════════════
// GMAIL SMTP EMAIL ENGINE — sends on fraud block
// ═══════════════════════════════════════════════════════════
// Email sent via FastAPI /send-email endpoint (Gmail SMTP — server-side)

async function sendResendEmail({ to, subject, html }) {
  const res = await fetch(API + '/send-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to: Array.isArray(to) ? to : [to], subject, html }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.message || 'Email send failed');
  console.log('[Email] Sent to', to);
  return data;
}

async function sendFraudEmails(caseNo) {
  if (!currentTxnCtx) return;
  const { result, payload } = currentTxnCtx;
  const sender  = payload.selectedUser;
  const recip   = RECIP_FULL[payload.recipientId] || RECIP_FULL['SBI0001'];
  const score   = Math.round((result.fraud_probability||0)*100);
  const txnId   = result.transaction_id || '—';
  const amount  = fmtINR(payload.amount);
  const now     = new Date().toLocaleString('en-IN',{dateStyle:'long',timeStyle:'medium'});
  const dist    = result.location_deviation_km || 0;
  const riskFactorsHtml = (result.risk_factors||[]).map(f =>
    `<li style="padding:4px 0;color:#555;border-bottom:1px solid #eee;">${f}</li>`).join('');

  // ── Email 1: VICTIM ALERT ──────────────────────────────────────────────
  const victimHtml = `
<!DOCTYPE html><html><head><meta charset="UTF-8"/><\/head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:30px 0;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#0a1628 0%,#0d2040 100%);padding:28px 36px;text-align:center;">
    <div style="font-size:33px;margin-bottom:8px;">🛡️</div>
    <h1 style="margin:0;font-size:27px;font-weight:700;color:#00f5d4;letter-spacing:1px;">VOIDGUARD AI</h1>
    <p style="margin:6px 0 0;font-size:17px;color:rgba(255,255,255,0.5);letter-spacing:2px;">FRAUD DETECTION SYSTEM</p>
  </td></tr>

  <!-- ALERT BANNER -->
  <tr><td style="background:#fff1f2;border-left:4px solid #ff3355;padding:16px 36px;">
    <p style="margin:0;font-size:19px;font-weight:700;color:#ff3355;">🚨 FRAUD ATTEMPT BLOCKED — YOUR ACCOUNT IS SAFE</p>
    <p style="margin:4px 0 0;font-size:17px;color:#888;">Case No: <strong>${caseNo}</strong> &nbsp;·&nbsp; ${now}</p>
  </td></tr>

  <!-- GREETING -->
  <tr><td style="padding:28px 36px 0;">
    <p style="margin:0;font-size:20px;color:#333;">Dear <strong>${sender.name}</strong>,</p>
    <p style="margin:12px 0 0;font-size:19px;color:#555;line-height:1.7;">
      Our AI fraud detection system detected and <strong style="color:#ff3355;">blocked a suspicious transaction</strong> on your ${sender.bank} account.
      You confirmed this was <strong>NOT initiated by you</strong>, so we have taken immediate action.
    </p>
  </td></tr>

  <!-- TXN DETAILS BOX -->
  <tr><td style="padding:20px 36px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8faff;border:1px solid #e0e8ff;border-radius:10px;overflow:hidden;">
      <tr><td colspan="2" style="padding:12px 18px;background:#0a1628;font-size:16px;font-weight:700;color:#00f5d4;letter-spacing:2px;text-transform:uppercase;">Transaction Details</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;width:44%;border-bottom:1px solid #eee;">Transaction ID</td><td style="padding:10px 18px;font-size:18px;font-weight:700;color:#ff3355;border-bottom:1px solid #eee;">${txnId}</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;border-bottom:1px solid #eee;">Amount Attempted</td><td style="padding:10px 18px;font-size:18px;font-weight:700;color:#ff3355;border-bottom:1px solid #eee;">${amount}</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;border-bottom:1px solid #eee;">Your Usual Location</td><td style="padding:10px 18px;font-size:18px;color:#333;border-bottom:1px solid #eee;">${sender.usual_location}</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;border-bottom:1px solid #eee;">Transaction Location</td><td style="padding:10px 18px;font-size:18px;font-weight:700;color:#ff3355;border-bottom:1px solid #eee;">${payload.currLoc} (${dist} km away)</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;border-bottom:1px solid #eee;">Risk Score</td><td style="padding:10px 18px;font-size:18px;font-weight:700;color:#ff3355;border-bottom:1px solid #eee;">${score}% — HIGH RISK</td></tr>
      <tr><td style="padding:10px 18px;font-size:18px;color:#888;">Status</td><td style="padding:10px 18px;font-size:18px;font-weight:700;color:#ff3355;">🚫 BLOCKED</td></tr>
    </table>
  </td></tr>

  <!-- YOUR ACCOUNT INFO -->
  <tr><td style="padding:0 36px 20px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fff8;border:1px solid #b2f5d4;border-radius:10px;overflow:hidden;">
      <tr><td colspan="2" style="padding:12px 18px;background:#006644;font-size:16px;font-weight:700;color:#fff;letter-spacing:2px;text-transform:uppercase;">Your Account (Protected)</td></tr>
      <tr><td style="padding:9px 18px;font-size:18px;color:#555;width:44%;border-bottom:1px solid #e0f5ea;">Account Holder</td><td style="padding:9px 18px;font-size:18px;color:#222;border-bottom:1px solid #e0f5ea;">${sender.name}</td></tr>
      <tr><td style="padding:9px 18px;font-size:18px;color:#555;border-bottom:1px solid #e0f5ea;">Bank</td><td style="padding:9px 18px;font-size:18px;color:#222;border-bottom:1px solid #e0f5ea;">${sender.bank} — ${sender.branch}</td></tr>
      <tr><td style="padding:9px 18px;font-size:18px;color:#555;border-bottom:1px solid #e0f5ea;">Account Number</td><td style="padding:9px 18px;font-size:18px;color:#222;border-bottom:1px solid #e0f5ea;">${sender.account}</td></tr>
      <tr><td style="padding:9px 18px;font-size:18px;color:#555;">IFSC</td><td style="padding:9px 18px;font-size:18px;color:#222;">${sender.ifsc}</td></tr>
    </table>
  </td></tr>

  <!-- AI EVIDENCE -->
  <tr><td style="padding:0 36px 20px;">
    <p style="margin:0 0 10px;font-size:18px;font-weight:700;color:#333;">Why our AI flagged this:</p>
    <ul style="margin:0;padding:0 0 0 18px;">${riskFactorsHtml}</ul>
  </td></tr>

  <!-- ACTIONS TAKEN -->
  <tr><td style="padding:0 36px 20px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff8e1;border:1px solid #ffe082;border-radius:10px;padding:16px;">
      <tr><td style="padding:0 0 8px;font-size:18px;font-weight:700;color:#b45309;">⚡ Actions Taken Automatically</td></tr>
      <tr><td style="font-size:18px;color:#555;line-height:2;">
        ✅ Transaction <strong>BLOCKED</strong> — your money is safe<br/>
        🚔 Cyber Crime complaint filed — Case: <strong>${caseNo}</strong><br/>
        🚩 Recipient account flagged in RBI Fraud Registry<br/>
        🏦 ${sender.bank} fraud team has been notified<br/>
        📁 Full report saved to our secure database
      </td></tr>
    </table>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#0a1628;padding:20px 36px;text-align:center;">
    <p style="margin:0;font-size:17px;color:rgba(255,255,255,0.4);">VoidGuard AI · Fraud Detection System · TechManthan 2026</p>
    <p style="margin:6px 0 0;font-size:16px;color:rgba(255,255,255,0.25);">Geetanjali Institute of Technical Studies · Team VOID</p>
  </td></tr>

</table>
</td></tr>
</table>
<\/body><\/html>`;

  // ── Email 2: CYBER CRIME / POLICE REPORT ──────────────────────────────
  const policeHtml = `
<!DOCTYPE html><html><head><meta charset="UTF-8"/><\/head>
<body style="margin:0;padding:0;background:#f4f4f7;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:30px 0;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#1a0408 0%,#3a0a10 100%);padding:28px 36px;text-align:center;">
    <div style="font-size:33px;margin-bottom:8px;">🚔</div>
    <h1 style="margin:0;font-size:25px;font-weight:700;color:#ff6b6b;letter-spacing:1px;">CYBER CRIME COMPLAINT</h1>
    <p style="margin:6px 0 0;font-size:16px;color:rgba(255,255,255,0.5);letter-spacing:2px;">AUTO-FILED BY VOIDGUARD AI · MINISTRY OF HOME AFFAIRS</p>
  </td></tr>

  <!-- CASE BANNER -->
  <tr><td style="background:#1a0408;padding:12px 36px;text-align:center;">
    <p style="margin:0;font-size:20px;color:#ff3355;font-weight:700;letter-spacing:1px;">CASE NO: ${caseNo}</p>
    <p style="margin:4px 0 0;font-size:16px;color:rgba(255,255,255,0.4);">${now} · cybercrime.gov.in portal</p>
  </td></tr>

  <!-- FRAUD SUMMARY -->
  <tr><td style="padding:24px 36px 0;">
    <p style="margin:0 0 14px;font-size:18px;font-weight:700;color:#333;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #ff3355;padding-bottom:8px;">📋 Fraud Summary</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ffd0d8;border-radius:8px;overflow:hidden;">
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;width:44%;border-bottom:1px solid #ffe0e6;">Transaction ID</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${txnId}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Amount Attempted</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${amount}</td></tr>
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Risk Score</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${score}% — ${result.confidence} CONFIDENCE</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Detection Model</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #ffe0e6;">XGBoost v2.1 — VoidGuard AI</td></tr>
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;">User Confirmed</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;">"NOT INITIATED BY ME"</td></tr>
    </table>
  </td></tr>

  <!-- VICTIM DETAILS -->
  <tr><td style="padding:20px 36px 0;">
    <p style="margin:0 0 12px;font-size:18px;font-weight:700;color:#333;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #2e7d32;padding-bottom:8px;">👤 Victim — Account Holder</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #c8e6c9;border-radius:8px;overflow:hidden;">
      <tr style="background:#f1f8e9;"><td style="padding:9px 16px;font-size:17px;color:#888;width:44%;border-bottom:1px solid #dcedc8;">Full Name</td><td style="padding:9px 16px;font-size:17px;font-weight:600;color:#222;border-bottom:1px solid #dcedc8;">${sender.name}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Bank</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.bank} · ${sender.branch}</td></tr>
      <tr style="background:#f1f8e9;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Account No</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.account}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">IFSC</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.ifsc}</td></tr>
      <tr style="background:#f1f8e9;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">PAN</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.pan}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Aadhaar</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.aadhaar}</td></tr>
      <tr style="background:#f1f8e9;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Mobile</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.phone}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Usual Location</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #dcedc8;">${sender.usual_location}</td></tr>
      <tr style="background:#f1f8e9;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #dcedc8;">Transaction Location</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #dcedc8;">${payload.currLoc} (${dist} km away)</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;">Address</td><td style="padding:9px 16px;font-size:17px;color:#333;">${sender.address}</td></tr>
    </table>
  </td></tr>

  <!-- SUSPECT DETAILS -->
  <tr><td style="padding:20px 36px 0;">
    <p style="margin:0 0 12px;font-size:18px;font-weight:700;color:#333;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #ff3355;padding-bottom:8px;">🚨 Suspect — Recipient / Destination Account</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ffd0d8;border-radius:8px;overflow:hidden;">
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;width:44%;border-bottom:1px solid #ffe0e6;">Account Name</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${recip.name}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Account Number</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${recip.account}</td></tr>
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Bank</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #ffe0e6;">${recip.bank} · ${recip.branch}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">IFSC</td><td style="padding:9px 16px;font-size:17px;color:#333;border-bottom:1px solid #ffe0e6;">${recip.ifsc}</td></tr>
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">PAN</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${recip.pan}</td></tr>
      <tr><td style="padding:9px 16px;font-size:17px;color:#888;border-bottom:1px solid #ffe0e6;">Total Transactions</td><td style="padding:9px 16px;font-size:17px;font-weight:700;color:#ff3355;border-bottom:1px solid #ffe0e6;">${recip.total_transactions || recip.total_txns || 0} txns (SUSPICIOUS)</td></tr>
      <tr style="background:#fff5f7;"><td style="padding:9px 16px;font-size:17px;color:#888;">Address</td><td style="padding:9px 16px;font-size:17px;color:#333;">${recip.address}</td></tr>
    </table>
  </td></tr>

  <!-- AI EVIDENCE -->
  <tr><td style="padding:20px 36px 24px;">
    <p style="margin:0 0 12px;font-size:18px;font-weight:700;color:#333;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #1565c0;padding-bottom:8px;">🧠 AI Evidence — XAI Risk Factors</p>
    <ul style="margin:0;padding:0 0 0 18px;">${riskFactorsHtml}</ul>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#1a0408;padding:20px 36px;text-align:center;">
    <p style="margin:0;font-size:17px;color:rgba(255,255,255,0.5);">This is an automated report from VoidGuard AI Fraud Detection</p>
    <p style="margin:6px 0 0;font-size:16px;color:rgba(255,255,255,0.3);">Case ${caseNo} · TechManthan 2026 · Team VOID · GITS</p>
  </td></tr>

</table>
</td></tr>
</table>
<\/body><\/html>`;

  // ── Send both emails ───────────────────────────────────────────────────
  const emailsToSend = [
    {
      to: 'lavishdadhich2006@gmail.com',  // victim alert email
      subject: `🚨 [${caseNo}] Fraud Blocked — Your ${sender.bank} Account is Protected`,
      html: victimHtml,
      label: 'Victim Alert'
    },
    {
      to: 'lavishdadhich20@gmail.com',  // cyber crime report email
      subject: `🚔 Cyber Crime Report — ${caseNo} — Fraud Attempt ${txnId} — ${amount}`,
      html: policeHtml,
      label: 'Cyber Crime Report' 
    }
  ];

  showToast('📧 Sending fraud alert emails…', 'info');

  let successCount = 0;
  for (const mail of emailsToSend) {
    try {
      await sendResendEmail({ to: mail.to, subject: mail.subject, html: mail.html });
      successCount++;
      console.log(`[Email] ✓ ${mail.label} sent`);
    } catch(e) {
      console.error(`[Email] ✗ ${mail.label} failed:`, e.message);
    }
  }

  if (successCount === emailsToSend.length) {
    showToast('📧 Both emails sent — Victim + Cyber Crime Cell', 'ok');
  } else if (successCount > 0) {
    showToast(`📧 ${successCount}/${emailsToSend.length} emails sent`, 'info');
  } else {
    showToast('📧 Email delivery failed — check console', 'err');
  }
}

function closeAlert() {
  const ov = document.getElementById('alert-overlay');
  if (ov) { ov.classList.add('hide'); setTimeout(()=>ov.remove(), 260); }
}

// ═══════════════════════════════════════════════════════════
// POLICE REPORT — full MongoDB account details
// ═══════════════════════════════════════════════════════════
const RECIP_FULL = {
  'SBI0001':{name:'Vikram Singh',bank:'State Bank of India',branch:'Jaipur Central',ifsc:'SBIN0001001',account:'XXXX XXXX 1001',pan:'LMNOP1001Q',address:'22 MI Road, Jaipur, Rajasthan 302001',total_txns:450,avg_inflow:2000},
  'SBI0002':{name:'Unknown / Mule Account',bank:'State Bank of India',branch:'Unknown Branch',ifsc:'SBIN0002002',account:'XXXX XXXX 2002',pan:'NOT REGISTERED',address:'Address not verified',total_txns:4,avg_inflow:300},
  'HDFC001':{name:'Meera Nair',bank:'HDFC Bank',branch:'Koregaon Park',ifsc:'HDFC0003003',account:'XXXX XXXX 3003',pan:'QRSTU3003V',address:'99 Koregaon Park, Pune, Maharashtra 411001',total_txns:1200,avg_inflow:15000},
};

function showPoliceReport() {
  if (!currentTxnCtx) return;
  const { result, payload } = currentTxnCtx;
  const sender = payload.selectedUser;
  const recip = RECIP_FULL[payload.recipientId] || RECIP_FULL['SBI0001'];
  const caseNo = currentTxnCtx._caseNo || ('CYB-'+new Date().getFullYear()+'-'+String(rand(10000,99999)));
  const now = new Date().toLocaleString('en-IN',{dateStyle:'long',timeStyle:'medium'});
  const score = Math.round((result.fraud_probability||0)*100);

  document.body.insertAdjacentHTML('beforeend', `
  <div class="overlay-bg" id="police-overlay">
    <div class="police-modal">
      <div class="police-hdr">
        <div class="police-hdr-icon">🚔</div>
        <div>
          <div class="police-hdr-title">CYBER CRIME COMPLAINT — TRANSACTION BLOCKED</div>
          <div class="police-hdr-sub">Auto-filed · Cyber Crime Division · Ministry of Home Affairs</div>
        </div>
        <div class="police-meta">
          <div class="police-case-no">${caseNo}</div>
          <div class="police-ts">${now}</div>
        </div>
      </div>
      <div class="police-body">

        <div class="status-bar">
          <div style="font-size:23px;">🚫</div>
          <div style="font-size:17px;color:var(--ts);line-height:1.5;">Transaction of <strong style="color:var(--red);">${fmtINR(payload.amount)}</strong> has been <strong style="color:var(--red);">BLOCKED</strong>. Complaint filed with <strong style="color:var(--tp);">Cyber Crime Cell</strong>. Both accounts flagged in RBI Fraud Registry. Result saved to <strong style="color:var(--tp);">MongoDB</strong>.</div>
        </div>

        <div class="psec">
          <div class="psec-title">Fraud Summary</div>
          <div class="report-grid">
            <div class="rf"><div class="rf-label">Case Number</div><div class="rf-val red">${caseNo}</div></div>
            <div class="rf"><div class="rf-label">Transaction ID</div><div class="rf-val red">${result.transaction_id||'—'}</div></div>
            <div class="rf"><div class="rf-label">Amount Attempted</div><div class="rf-val red">${fmtINR(payload.amount)}</div></div>
            <div class="rf"><div class="rf-label">Risk Score</div><div class="rf-val red">${score}% — ${result.confidence}</div></div>
            <div class="rf"><div class="rf-label">Filed On</div><div class="rf-val">${now}</div></div>
            <div class="rf"><div class="rf-label">Detection Model</div><div class="rf-val">XGBoost v2.1 · VoidGuard AI</div></div>
          </div>
        </div>

        <div class="psec">
          <div class="psec-title">Victim — Sender / Account Holder</div>
          <div class="report-grid">
            <div class="rf"><div class="rf-label">Full Name</div><div class="rf-val">${sender.name}</div></div>
            <div class="rf"><div class="rf-label">User ID</div><div class="rf-val">${sender._id}</div></div>
            <div class="rf"><div class="rf-label">Bank Name</div><div class="rf-val">${sender.bank||'—'}</div></div>
            <div class="rf"><div class="rf-label">Branch</div><div class="rf-val">${sender.branch||'—'}</div></div>
            <div class="rf"><div class="rf-label">Account Number</div><div class="rf-val">${sender.account||'—'}</div></div>
            <div class="rf"><div class="rf-label">IFSC Code</div><div class="rf-val">${sender.ifsc||'—'}</div></div>
            <div class="rf"><div class="rf-label">PAN Number</div><div class="rf-val">${sender.pan||'—'}</div></div>
            <div class="rf"><div class="rf-label">Aadhaar (masked)</div><div class="rf-val">${sender.aadhaar||'—'}</div></div>
            <div class="rf"><div class="rf-label">Mobile</div><div class="rf-val">${sender.phone||'—'}</div></div>
            <div class="rf"><div class="rf-label">Email</div><div class="rf-val">${sender.email||'—'}</div></div>
            <div class="rf full"><div class="rf-label">Registered Address</div><div class="rf-val">${sender.address||'—'}</div></div>
            <div class="rf"><div class="rf-label">Usual Location</div><div class="rf-val">${sender.usual_location}</div></div>
            <div class="rf"><div class="rf-label">Transaction Location</div><div class="rf-val red">${payload.currLoc} (${result.location_deviation_km||0} km away)</div></div>
          </div>
        </div>

        <div class="psec">
          <div class="psec-title">Suspect — Recipient / Destination Account</div>
          <div class="report-grid">
            <div class="rf"><div class="rf-label">Account Name</div><div class="rf-val red">${recip.name}</div></div>
            <div class="rf"><div class="rf-label">Account Number</div><div class="rf-val red">${recip.account}</div></div>
            <div class="rf"><div class="rf-label">Bank</div><div class="rf-val">${recip.bank}</div></div>
            <div class="rf"><div class="rf-label">Branch</div><div class="rf-val">${recip.branch}</div></div>
            <div class="rf"><div class="rf-label">IFSC</div><div class="rf-val">${recip.ifsc}</div></div>
            <div class="rf"><div class="rf-label">PAN</div><div class="rf-val red">${recip.pan}</div></div>
            <div class="rf"><div class="rf-label">Total Past Txns</div><div class="rf-val red">${recip.total_txns} txns</div></div>
            <div class="rf"><div class="rf-label">Avg Inflow</div><div class="rf-val">${fmtINR(recip.avg_inflow)}</div></div>
            <div class="rf full"><div class="rf-label">Address</div><div class="rf-val">${recip.address}</div></div>
          </div>
        </div>

        <div class="psec">
          <div class="psec-title">AI Evidence — XAI Risk Factors</div>
          <div class="ev-box">${(result.risk_factors||[]).concat([
            `Distance from usual: ${result.location_deviation_km||0} km`,
            `Amount deviation: ${result.amount_deviation_ratio||'—'}x above average`,
            'User confirmed: "This was NOT initiated by me"',
            `Saved to MongoDB · Case: ${caseNo}`
          ]).map(rf=>`<div class="ev-item"><div class="ev-dot"></div><div class="ev-text">${rf}</div></div>`).join('')}</div>
        </div>

        <div class="psec">
          <div class="psec-title">Actions Taken</div>
          <div class="actions-taken">
            <div class="at-item"><div class="at-ico">🚫</div><div class="at-text"><strong>Transaction BLOCKED</strong></div></div>
            <div class="at-item"><div class="at-ico">✅</div><div class="at-text"><strong>Sender Account Protected</strong></div></div>
            <div class="at-item"><div class="at-ico">🚩</div><div class="at-text"><strong>Recipient Flagged</strong> in RBI Registry</div></div>
            <div class="at-item"><div class="at-ico">📁</div><div class="at-text"><strong>Case Filed</strong> · ${caseNo}</div></div>
            <div class="at-item"><div class="at-ico">🏦</div><div class="at-text"><strong>${sender.bank||'Bank'} Notified</strong></div></div>
            <div class="at-item"><div class="at-ico">🗄</div><div class="at-text"><strong>MongoDB Saved</strong> · fraud_db</div></div>
          </div>
        </div>
      </div>
      <div class="police-footer">
        <button class="print-btn" onclick="window.print()">🖨 Print Report</button>
        <button class="dismiss-btn" onclick="closePolice()">Dismiss</button>
        <div class="filed-badge">⚡ AUTO-FILED · Cyber Crime Portal</div>
      </div>
    </div>
  </div>`);

  showToast('🚔 Report filed to Cyber Crime Cell · Saved to MongoDB', 'err');
}

function closePolice() {
  const ov = document.getElementById('police-overlay');
  if (ov) { ov.classList.add('hide'); setTimeout(()=>ov.remove(), 260); }
}

// ═══════════════════════════════════════════════════════════
// MISC
// ═══════════════════════════════════════════════════════════
function saveApi() {
  API = document.getElementById('api-url').value.trim().replace(/\/$/, '') || API;
  const el = document.getElementById('api-sl');
  el.className = 'api-sl info'; el.textContent = `// Saved → ${API}`;
  checkDB().then(ok => {
    if (ok) { el.className='api-sl ok'; el.textContent='// ✓ Connected to MongoDB via FastAPI'; loadUserCards(); loadDashboard(); }
    else { el.className='api-sl err'; el.textContent='// Cannot reach API — start: uvicorn api_v2:app --host 0.0.0.0 --port 8000 --reload'; }
  });
}

function animNum(id, end) {
  const el = document.getElementById(id); if(!el) return;
  let v=0; const steps=1200/16; const inc=end/steps;
  const t=setInterval(()=>{v=Math.min(v+inc,end);el.textContent=Math.round(v).toLocaleString('en-IN');if(v>=end)clearInterval(t);},16);
}

function showToast(msg, type='info') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = `toast t-${type} show`;
  setTimeout(()=>t.className='toast', 3500);
}

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════
(async function init() {
  await loadUserCards();
  await loadDashboard();
  // Auto-refresh live table every 15s
  setInterval(() => {
    if (document.getElementById('page-dashboard').classList.contains('active')) {
      loadDashboard().catch(()=>{});
    }
  }, 15000);
})();


// ═══════════════════════════════════════════════════════════
// BURST FRAUD DETECTION — uses /simulate/burst from api.py
// ═══════════════════════════════════════════════════════════

// Fraud & Legit templates mirrored from test_prediction.py
const BURST_FRAUD_TEMPLATES = [
  { type:'Credential Theft',  desc:'Stolen credentials used from abroad, massive amount spike',    amt:[15,35], hour:[0,5],  device:0, usual:'delhi',     currLat:40.71, currLon:-74.00, vel:[1,3]  },
  { type:'Account Takeover',  desc:'New device, rapid transactions draining account',              amt:[8,20],  hour:[0,6],  device:0, usual:'mumbai',    current:'mumbai',              vel:[6,15] },
  { type:'Location Anomaly',  desc:'Transaction initiated from far-away location, new device',     amt:[5,12],  hour:[0,23], device:0, usual:'jaipur',    current:'kolkata',             vel:[0,3]  },
  { type:'Velocity Attack',   desc:'Burst of transactions in 15 minutes from new device',          amt:[2,6],   hour:[0,23], device:0, usual:'bengaluru', current:'bengaluru',           vel:[8,20] },
  { type:'Stealth Fraud',     desc:'Multiple moderate signals combined — night, distance, new device', amt:[4,9], hour:[0,5], device:0, usual:'chennai', current:'delhi',              vel:[2,5]  },
];

const BURST_LEGIT_TEMPLATES = [
  { type:'Normal UPI',        desc:'Everyday small payment, same city, known device',              amt:[0.3,1.5], hour:[8,22],  device:1, usual:'delhi',    current:'delhi',    vel:[0,1] },
  { type:'Bill Payment',      desc:'Utility or subscription, known device, daytime',               amt:[0.5,2.0], hour:[9,20],  device:1, usual:'mumbai',   current:'mumbai',   vel:[0,1] },
  { type:'Weekend Shopping',  desc:'Slightly elevated amount, known device, afternoon',            amt:[1.5,3.0], hour:[11,20], device:1, usual:'bengaluru',current:'mysuru',   vel:[0,2] },
  { type:'Business Travel',   desc:'User travelling, known device, normal amount',                 amt:[0.8,2.0], hour:[8,22],  device:1, usual:'delhi',    current:'jaipur',   vel:[0,1] },
  { type:'Late Night Transfer',desc:'Odd hour but known device, normal amount, same city',         amt:[0.5,1.5], hour:[0,5],   device:1, usual:'jaipur',   current:'jaipur',   vel:[0,1] },
];

function burstRandBetween(lo, hi) {
  return lo + Math.random() * (hi - lo);
}
function burstRandInt(lo, hi) {
  return Math.floor(lo + Math.random() * (hi - lo + 1));
}
function burstPickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function buildBurstTransaction(template, isFraud) {
  const senderAvg = burstRandBetween(500, 8000);
  const amt = Math.min(500000, Math.max(10, senderAvg * burstRandBetween(template.amt[0], template.amt[1])));
  const hour = burstRandInt(template.hour[0], template.hour[1]);
  const vel  = burstRandInt(template.vel[0], template.vel[1]);

  const txn = {
    transaction_amount:      Math.round(amt),
    transaction_hour:        hour,
    device_id_match:         template.device,
    sender_avg_txn_amount:   Math.round(senderAvg),
    transactions_last_15min: vel,
    sender_usual_location:   template.usual,
  };
  if (template.currLat !== undefined) {
    txn.current_txn_lat = template.currLat;
    txn.current_txn_lon = template.currLon;
  } else {
    txn.current_txn_location = template.current;
  }
  return { txn, label: isFraud ? 1 : 0, type: template.type, desc: template.desc, senderAvg };
}

function selectBurstCount(n, btn) {
  document.getElementById('burst-count').value = n;
  document.querySelectorAll('.burst-count-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const nFraud = Math.max(1, Math.round(n * 0.35));
  document.getElementById('burst-count-hint').textContent = nFraud + ' fraud + ' + (n - nFraud) + ' legit';
}

function openBurst() {
  const ov = document.getElementById('burst-overlay');
  ov.style.display = 'flex';
  ov.classList.remove('hide');
  // Always show landing on open
  document.getElementById('burst-landing').style.display = 'flex';
  document.getElementById('burst-results-screen').style.display = 'none';
  document.getElementById('burst-running-tag').style.display = 'none';
}

function closeBurst() {
  const ov = document.getElementById('burst-overlay');
  ov.classList.add('hide');
  setTimeout(() => { ov.style.display = 'none'; ov.classList.remove('hide'); }, 260);
}

function resetBurst() {
  document.getElementById('burst-landing').style.display = 'flex';
  document.getElementById('burst-results-screen').style.display = 'none';
  document.getElementById('burst-running-tag').style.display = 'none';
  const btn = document.getElementById('burst-run-btn');
  btn.disabled = false;
  btn.innerHTML = '<span style="font-size:21px;">▶</span> RUN BURST DETECTION';
}

async function runBurst() {
  const n    = parseInt(document.getElementById('burst-count').value);
  const btn  = document.getElementById('burst-run-btn');
  const tag  = document.getElementById('burst-running-tag');

  // Switch to results screen
  document.getElementById('burst-landing').style.display = 'none';
  const resultsScreen = document.getElementById('burst-results-screen');
  resultsScreen.style.display = 'flex';

  const sub   = document.getElementById('burst-subtitle-results');
  const prog  = document.getElementById('burst-progress-wrap');
  const fill  = document.getElementById('burst-progress-fill');
  const ptext = document.getElementById('burst-progress-text');
  const step  = document.getElementById('burst-step-text');
  const cont  = document.getElementById('burst-content');

  btn.disabled = true; btn.innerHTML = '<span style="font-size:21px;">⏳</span> RUNNING…';
  tag.style.display = 'inline-block';
  sub.textContent = `Analyzing ${n} transactions through XGBoost model…`;
  prog.style.display = 'block';
  fill.style.width = '0%';
  ptext.textContent = '0 / ' + n;

  // Build transactions: ~35% fraud
  const nFraud = Math.max(1, Math.round(n * 0.35));
  const nLegit = n - nFraud;
  let allTxns = [];
  for (let i = 0; i < nFraud; i++) allTxns.push(buildBurstTransaction(burstPickRandom(BURST_FRAUD_TEMPLATES), true));
  for (let i = 0; i < nLegit; i++) allTxns.push(buildBurstTransaction(burstPickRandom(BURST_LEGIT_TEMPLATES), false));
  // Shuffle
  allTxns = allTxns.sort(() => Math.random() - 0.5);

  // Try real API first
  let useRealAPI = false;
  try {
    await fetch(API + '/health', { signal: AbortSignal.timeout(2000) });
    useRealAPI = true;
  } catch { useRealAPI = false; }

  // Show table header
  cont.innerHTML = `
    <div class="burst-table-wrap">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);width:36px;">#</th>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);">Type</th>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);">Amount</th>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);">Ground Truth</th>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);">Model Says</th>
            <th style="font-family:var(--mono);font-size:13px;letter-spacing:2px;color:var(--tm);text-transform:uppercase;padding:9px 12px;text-align:left;background:rgba(0,0,0,.3);border-bottom:1px solid var(--b);">Risk / Match</th>
          </tr>
        </thead>
        <tbody id="burst-tbody"></tbody>
      </table>
    </div>`;

  const tbody = document.getElementById('burst-tbody');
  const results = [];
  const STEPS_LABELS = ['Fetching sender profile…','Computing Haversine distance…','Running XGBoost inference…','Evaluating risk factors…'];
  let stepIdx = 0;

  for (let i = 0; i < allTxns.length; i++) {
    const { txn, label: trueLabel, type: txnType, desc, senderAvg } = allTxns[i];
    fill.style.width = ((i / n) * 100) + '%';
    ptext.textContent = i + ' / ' + n;
    step.textContent = STEPS_LABELS[stepIdx % STEPS_LABELS.length];
    stepIdx++;

    let result = null;
    if (useRealAPI) {
      try {
        const params = new URLSearchParams({
          transaction_amount:      txn.transaction_amount,
          transaction_hour:        txn.transaction_hour,
          device_id_match:         txn.device_id_match,
          sender_avg_txn_amount:   txn.sender_avg_txn_amount,
          transactions_last_15min: txn.transactions_last_15min,
          model_name: 'xgboost', threshold: 0.5
        });
        if (txn.sender_usual_location) params.append('sender_usual_location', txn.sender_usual_location);
        if (txn.current_txn_location)  params.append('current_txn_location', txn.current_txn_location);
        if (txn.current_txn_lat !== undefined) { params.append('current_txn_lat', txn.current_txn_lat); params.append('current_txn_lon', txn.current_txn_lon); }
        const res = await fetch(API + '/predict?' + params, { method:'POST', signal:AbortSignal.timeout(5000) });
        if (res.ok) result = await res.json();
      } catch { useRealAPI = false; }
    }

    // Fallback simulation using same logic as simulateOffline
    if (!result) result = simulateOffline({
      amount: txn.transaction_amount, currLoc: txn.current_txn_location || 'delhi',
      hour: txn.transaction_hour, deviceVal: txn.device_id_match === 1 ? 'known' : 'unknown',
      v15: txn.transactions_last_15min, recip: { avg: 2000, count: 300 },
      selectedUser: { usual_location: txn.sender_usual_location || 'delhi', avg_txn_amount: senderAvg, _id:'burst_user' }
    });

    const prob    = result.fraud_probability || 0;
    const predLabel = result.label;
    const correct = predLabel === trueLabel;

    // Pill color
    const pillClass = prob > 0.7 ? 'high' : prob > 0.4 ? 'med' : 'low';
    const pillText  = Math.round(prob * 100) + '%';
    const trueBadge = trueLabel === 1
      ? '<span class="badge fraud">FRAUD</span>'
      : '<span class="badge safe">LEGIT</span>';
    const predBadge = predLabel === 1
      ? '<span class="badge fraud">FRAUD</span>'
      : '<span class="badge safe">LEGIT</span>';
    const matchIcon = correct
      ? '<span class="burst-match-ok">✓</span>'
      : '<span class="burst-match-fail">✗</span>';

    const tr = document.createElement('tr');
    tr.style.cssText = 'animation:rowIn .2s ease;border-bottom:1px solid rgba(12,29,54,.4);';
    tr.innerHTML = `
      <td style="padding:9px 12px;font-family:var(--mono);font-size:15px;color:var(--tm);">${i+1}</td>
      <td style="padding:9px 12px;">
        <div style="font-size:17px;color:var(--tp);">${txnType}</div>
        <div style="font-size:15px;color:var(--ts);margin-top:1px;">${desc.substring(0,44)}…</div>
      </td>
      <td style="padding:9px 12px;font-family:var(--mono);font-size:16px;color:var(--tp);">${fmtINR(txn.transaction_amount)}</td>
      <td style="padding:9px 12px;">${trueBadge}</td>
      <td style="padding:9px 12px;">${predBadge}</td>
      <td style="padding:9px 12px;display:flex;align-items:center;gap:10px;">
        <span class="risk-pill ${pillClass}">${pillText}</span>
        ${matchIcon}
      </td>`;
    tbody.appendChild(tr);

    results.push({ txnType, desc, trueLabel, predLabel, prob, correct, amount: txn.transaction_amount });

    // Small delay for dramatic effect
    await new Promise(r => setTimeout(r, 60));
  }

  // Complete progress
  fill.style.width = '100%';
  ptext.textContent = n + ' / ' + n;
  step.textContent = '✓ Analysis complete';
  tag.style.display = 'none';
  prog.style.display = 'none';
  sub.textContent = `Results: ${n} transactions analyzed`;
  btn.disabled = false;
  btn.innerHTML = '<span style="font-size:21px;">▶</span> RUN BURST DETECTION';

  // Build summary
  renderBurstSummary(results, n, useRealAPI);
  showToast(`⚡ Burst complete — ${n} transactions analyzed`, 'ok');
}

// ═══════════════════════════════════════════════════════════
// TRANSACTION DETAIL MODAL
// ═══════════════════════════════════════════════════════════
function openTxnDetail(idx) {
  const t = (window._logTransactions || [])[idx];
  if (!t) return;

  const status = t.status || 'SAFE';
  const isFraud = status === 'FRAUD';
  const isReview = status === 'REVIEW';
  const isSafe = status === 'SAFE';

  const clr = isFraud ? 'var(--red)' : isReview ? 'var(--orange)' : 'var(--green)';
  const barClr = isFraud ? '#ff3355' : isReview ? '#ffb800' : '#00e676';
  const icon = isFraud ? '🚨' : isReview ? '⚠️' : '✅';
  const score = Math.round((t.fraud_probability || 0) * 100);

  // Modal class
  const modal = document.getElementById('txn-detail-modal');
  modal.className = 'txn-modal ' + (isFraud ? 'fraud-modal' : isReview ? 'review-modal' : 'safe-modal');

  // Header
  const hdr = document.getElementById('txn-mhdr');
  hdr.className = 'txn-mhdr ' + (isFraud ? 'fraud-hdr' : isReview ? 'review-hdr' : 'safe-hdr');
  const icoEl = document.getElementById('txn-mhdr-icon');
  icoEl.className = 'txn-mhdr-icon ' + (isFraud ? 'fraud-ico' : isReview ? 'review-ico' : 'safe-ico');
  icoEl.textContent = icon;
  document.getElementById('txn-mhdr-title').textContent =
    isFraud ? 'Fraud Detected' : isReview ? 'Flagged for Review' : 'Safe Transaction';
  document.getElementById('txn-mhdr-sub').textContent =
    isFraud ? 'This transaction was flagged as fraudulent by VoidGuard AI'
    : isReview ? 'This transaction requires manual review'
    : 'This transaction was cleared as legitimate';
  document.getElementById('txn-mhdr-id').textContent = t.transaction_id || '—';
  document.getElementById('txn-mhdr-ts').textContent = t.timestamp
    ? new Date(t.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—';

  // Risk banner
  const banner = document.getElementById('txn-risk-banner');
  banner.className = 'txn-risk-banner ' + (isFraud ? 'fraud-ban' : isReview ? 'review-ban' : 'safe-ban');
  document.getElementById('txn-risk-label').textContent = isFraud ? '🔴 FRAUD SCORE' : isReview ? '🟡 RISK SCORE' : '🟢 RISK SCORE';
  document.getElementById('txn-risk-label').style.color = clr;
  document.getElementById('txn-risk-score').textContent = score + '%';
  document.getElementById('txn-risk-score').style.color = clr;
  document.getElementById('txn-risk-score').style.textShadow = `0 0 20px ${clr}55`;
  document.getElementById('txn-risk-conf').textContent = 'Confidence: ' + (t.confidence || '—');
  document.getElementById('txn-risk-thresh').textContent = 'Threshold: 50% · Model decision: ' + status;

  // Animate bar
  const bar = document.getElementById('txn-risk-bar');
  bar.style.width = '0%';
  bar.style.background = barClr;
  bar.style.boxShadow = `0 0 10px ${barClr}55`;
  setTimeout(() => { bar.style.width = score + '%'; }, 80);

  // Transaction info
  const devMatch = t.device_match === 1 || t.device_match === true;
  document.getElementById('td-amount').textContent = fmtINR(t.transaction_amount || 0);
  document.getElementById('td-amount').className = 'txn-df-val mono ' + (isFraud ? 'red' : isSafe ? 'green' : 'amber');
  document.getElementById('td-status').innerHTML = `<span class="badge ${status.toLowerCase()}">${status}</span>`;
  document.getElementById('td-hour').textContent = String(t.transaction_hour ?? '—').padStart(2, '0') + ':00';
  document.getElementById('td-device').textContent = devMatch ? '✓ Known Device' : '✗ Unknown Device';
  document.getElementById('td-device').className = 'txn-df-val ' + (devMatch ? 'green' : 'red');
  document.getElementById('td-v15').textContent = (t.transactions_last_15min ?? '—') + ' transactions';
  document.getElementById('td-v15').className = 'txn-df-val mono ' + ((t.transactions_last_15min || 0) >= 3 ? 'red' : 'green');
  document.getElementById('td-latency').textContent = (t.latency_ms || '—') + ' ms';
  document.getElementById('td-deviceid').textContent = t.device_id || '—';

  // Location
  const dist = t.location_deviation_km || 0;
  document.getElementById('td-usual-loc').textContent = t.usual_location || '—';
  document.getElementById('td-curr-loc').textContent = t.current_txn_location || '—';
  const distEl = document.getElementById('td-dist');
  distEl.textContent = dist + ' km';
  distEl.style.background = dist > 500 ? 'var(--rdim)' : dist > 100 ? 'var(--adim)' : 'var(--gdim)';
  distEl.style.color = dist > 500 ? 'var(--red)' : dist > 100 ? 'var(--orange)' : 'var(--green)';
  distEl.style.border = dist > 500 ? '1px solid rgba(255,51,85,.2)' : dist > 100 ? '1px solid rgba(255,184,0,.2)' : '1px solid rgba(0,230,118,.18)';

  // Sender
  document.getElementById('td-username').textContent = t.user_name || t.user_id || '—';
  document.getElementById('td-userid').textContent = t.user_id || '—';
  // avg txn amount — compute from deviation ratio if available
  const avgAmt = t.amount_deviation_ratio && t.transaction_amount
    ? Math.round(t.transaction_amount / t.amount_deviation_ratio) : null;
  document.getElementById('td-avgamt').textContent = avgAmt ? fmtINR(avgAmt) : '—';
  const devRatio = t.amount_deviation_ratio || 0;
  document.getElementById('td-amtdev').textContent = devRatio ? devRatio.toFixed(2) + 'x average' : '—';
  document.getElementById('td-amtdev').className = 'txn-df-val ' + (devRatio >= 5 ? 'red' : devRatio >= 2 ? 'amber' : 'green');

  // Recipient
  document.getElementById('td-recip-avg').textContent = t.recipient_avg_inflow ? fmtINR(t.recipient_avg_inflow) : '—';
  const histCount = t.recipient_txn_history_count || 0;
  document.getElementById('td-recip-hist').textContent = histCount + ' transactions';
  document.getElementById('td-recip-hist').className = 'txn-df-val mono ' + (histCount < 10 ? 'red' : histCount < 50 ? 'amber' : 'green');

  // Risk factors
  const rfTitle = document.getElementById('txn-rf-title');
  rfTitle.className = 'txn-section-title ' + (isSafe ? 'green-sec' : 'red-sec');
  rfTitle.textContent = isSafe ? '✅ Risk Assessment' : '⚠ Risk Factors Detected';
  const factors = t.risk_factors || ['No significant risk factors'];
  document.getElementById('td-risk-factors').innerHTML = factors.map(rf => {
    const isHigh = /high|fraud|drain|unusual|unknown/i.test(rf);
    const isAmber = /moderate|mild|suspicious/i.test(rf);
    const dotClr = isHigh ? 'var(--red)' : isAmber ? 'var(--orange)' : 'var(--teal)';
    return `<div class="txn-rf-item">
      <div class="txn-rf-dot" style="background:${dotClr};box-shadow:0 0 5px ${dotClr}44;"></div>
      <div class="txn-rf-text">${rf}</div>
    </div>`;
  }).join('');


  document.getElementById('td-conf').textContent = t.confidence || '—';
  document.getElementById('td-conf').className = 'txn-df-val ' + (t.confidence === 'HIGH' ? (isFraud ? 'red' : 'green') : 'amber');

  const overlay = document.getElementById('txn-detail-overlay');
  overlay.style.display = 'flex';
  overlay.classList.remove('hide');
  document.body.style.overflow = 'hidden';
}

function closeTxnDetail(e) {
  if (e.target === document.getElementById('txn-detail-overlay')) {
    closeTxnDetailDirect();
  }
}

function closeTxnDetailDirect() {
  const overlay = document.getElementById('txn-detail-overlay');
  overlay.classList.add('hide');
  setTimeout(() => {
    overlay.style.display = 'none';
    overlay.classList.remove('hide');
    document.body.style.overflow = '';
  }, 200);
}

// Close on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    const overlay = document.getElementById('txn-detail-overlay');
    if (overlay && overlay.style.display !== 'none') closeTxnDetailDirect();
  }
});


  const total      = results.length;
  const actFraud   = results.filter(r => r.trueLabel === 1).length;
  const actLegit   = total - actFraud;
  const detected   = results.filter(r => r.trueLabel === 1 && r.predLabel === 1).length;
  const falsePos   = results.filter(r => r.trueLabel === 0 && r.predLabel === 1).length;
  const falseNeg   = results.filter(r => r.trueLabel === 1 && r.predLabel === 0).length;
  const correct    = results.filter(r => r.correct).length;
  const accuracy   = total ? Math.round(correct / total * 100) : 0;
  const recall     = actFraud ? Math.round(detected / actFraud * 100) : 0;

  // Type breakdown
  const typeCounts = {};
  results.forEach(r => { typeCounts[r.txnType] = (typeCounts[r.txnType] || 0) + 1; });

  const misses = results.filter(r => !r.correct);

  const summaryHTML = `
    <div class="burst-sum-stat" style="background:var(--rdim);border-color:rgba(255,51,85,.2);">
      <div class="burst-sum-label">Fraud Detected</div>
      <div class="burst-sum-val" style="color:var(--red);">${detected} <span style="font-size:19px;color:var(--ts);">/ ${actFraud}</span></div>
      <div class="burst-sum-sub">${recall}% recall rate</div>
      <div class="burst-metric-bar"><div class="burst-metric-fill" style="width:${recall}%;background:var(--red);"></div></div>
    </div>

    <div class="burst-sum-grid">
      <div class="burst-sum-stat">
        <div class="burst-sum-label">Accuracy</div>
        <div class="burst-sum-val" style="color:${accuracy>=85?'var(--green)':'var(--orange)'};">${accuracy}%</div>
        <div class="burst-metric-bar"><div class="burst-metric-fill" style="width:${accuracy}%;background:${accuracy>=85?'var(--green)':'var(--orange)'};"></div></div>
      </div>
      <div class="burst-sum-stat">
        <div class="burst-sum-label">Total Scanned</div>
        <div class="burst-sum-val" style="color:var(--blue);">${total}</div>
        <div class="burst-sum-sub">${actFraud} fraud · ${actLegit} legit</div>
      </div>
    </div>

    <div class="burst-sum-grid">
      <div class="burst-sum-stat">
        <div class="burst-sum-label">False Positives</div>
        <div class="burst-sum-val" style="color:${falsePos===0?'var(--green)':'var(--orange)'};">${falsePos}</div>
        <div class="burst-sum-sub">Legit blocked</div>
      </div>
      <div class="burst-sum-stat">
        <div class="burst-sum-label">Missed Fraud</div>
        <div class="burst-sum-val" style="color:${falseNeg===0?'var(--green)':'var(--red)'};">${falseNeg}</div>
        <div class="burst-sum-sub">False negatives</div>
      </div>
    </div>

    <div class="burst-sum-stat" style="margin-bottom:12px;">
      <div class="burst-sum-label" style="margin-bottom:8px;">Transaction Types</div>
      ${Object.entries(typeCounts).map(([type, count]) => `
        <div class="burst-type-row">
          <span class="burst-type-name">${type}</span>
          <span class="burst-type-count" style="color:var(--blue);">${count}</span>
        </div>`).join('')}
    </div>

    ${misses.length > 0 ? `
    <div class="burst-sum-stat" style="background:rgba(255,184,0,.04);border-color:rgba(255,184,0,.18);">
      <div class="burst-sum-label" style="color:var(--orange);margin-bottom:8px;">Misclassified (${misses.length})</div>
      ${misses.map(r => `
        <div style="padding:5px 0;border-bottom:1px solid var(--b);font-size:15px;">
          <div style="color:var(--tp);">${r.txnType}</div>
          <div style="color:var(--ts);">Truth: ${r.trueLabel===1?'FRAUD':'LEGIT'} → Model: ${r.predLabel===1?'FRAUD':'LEGIT'} · ${Math.round(r.prob*100)}%</div>
        </div>`).join('')}
    </div>` : `
    <div class="burst-sum-stat" style="background:var(--gdim);border-color:rgba(0,230,118,.18);text-align:center;padding:14px;">
      <div style="font-size:25px;margin-bottom:4px;">✅</div>
      <div style="font-family:var(--mono);font-size:14px;color:var(--green);letter-spacing:1px;">PERFECT DETECTION</div>
      <div style="font-size:16px;color:var(--ts);margin-top:3px;">All ${total} correctly classified</div>
    </div>`}

    <div style="font-family:var(--mono);font-size:13px;color:var(--tm);letter-spacing:1px;margin-top:10px;text-align:center;">
      ${usedRealAPI ? '// Results from XGBoost model via FastAPI' : '// Demo mode — offline simulation'}
    </div>`;

  document.getElementById('burst-summary-content').innerHTML = summaryHTML;


