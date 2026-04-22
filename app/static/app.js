// ─── State ─────────────────────────────────────────────────────────────────
let token = localStorage.getItem('token') || null;
let currentPlan = null;
let availableCombinations = [];

// ─── Bootstrap ─────────────────────────────────────────────────────────────
window.onload = async () => {
  if (token) {
    await enterApp();
  }
};

// ─── Auth helpers ──────────────────────────────────────────────────────────
function switchTab(tab) {
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Logging in...';

  const body = new URLSearchParams({
    username: document.getElementById('login-email').value,
    password: document.getElementById('login-password').value,
  });

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    token = data.access_token;
    localStorage.setItem('token', token);
    await enterApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Login</span>';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('register-btn');
  const errEl = document.getElementById('register-error');
  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating account...';

  try {
    const res = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        full_name: document.getElementById('reg-name').value || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');
    // Auto-login after register
    document.getElementById('login-email').value = document.getElementById('reg-email').value;
    document.getElementById('login-password').value = document.getElementById('reg-password').value;
    switchTab('login');
    await handleLogin({ preventDefault: () => {} });
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Create Account</span>';
  }
}

async function enterApp() {
  // Get user info
  try {
    const res = await fetch('/api/v1/auth/me', { headers: authHeader() });
    if (!res.ok) { logout(); return; }
    const user = await res.json();
    document.getElementById('user-badge').textContent = user.email;
  } catch { logout(); return; }

  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
  await loadCombinations();
}

function logout() {
  token = null;
  localStorage.removeItem('token');
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

function authHeader() {
  return { Authorization: `Bearer ${token}` };
}

// ─── Navigation ────────────────────────────────────────────────────────────
function showSection(name) {
  ['generate', 'saved'].forEach(s => {
    document.getElementById(`section-${s}`).classList.toggle('hidden', s !== name);
  });
  document.querySelectorAll('.nav-item').forEach((el, i) => {
    el.classList.toggle('active', ['generate', 'saved'][i] === name);
  });
  if (name === 'saved') loadSavedPlans();
}

// ─── Destination / Role combos ─────────────────────────────────────────────
async function loadCombinations() {
  try {
    const res = await fetch('/api/v1/info');
    const data = await res.json();
    availableCombinations = data.available_destinations || [];
    populateDestinations();
  } catch { console.error('Failed to load combinations'); }
}

function populateDestinations() {
  const destSel = document.getElementById('destination');
  const dests = [...new Set(availableCombinations.map(c => c.destination))];
  destSel.innerHTML = dests.map(d =>
    `<option value="${d}">${formatSlug(d)}</option>`
  ).join('');
  destSel.onchange = populateRoles;
  populateRoles();
}

function populateRoles() {
  const dest = document.getElementById('destination').value;
  const roles = availableCombinations.filter(c => c.destination === dest).map(c => c.role);
  const roleSel = document.getElementById('target-role');
  roleSel.innerHTML = roles.map(r =>
    `<option value="${r}">${formatSlug(r)}</option>`
  ).join('');
}

function formatSlug(slug) {
  return slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// ─── Generate Plan ──────────────────────────────────────────────────────────
async function handleGeneratePlan(e) {
  e.preventDefault();
  const btn = document.getElementById('generate-btn');
  const errEl = document.getElementById('plan-error');
  errEl.classList.add('hidden');
  document.getElementById('result-panel').classList.add('hidden');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating...';

  const payload = {
    origin: document.getElementById('origin').value,
    destination: formatSlug(document.getElementById('destination').value),
    target_role: formatSlug(document.getElementById('target-role').value),
    salary_expectation: parseFloat(document.getElementById('salary').value),
    timeline_months: parseInt(document.getElementById('timeline').value),
    work_authorisation_status: document.getElementById('work-auth').value,
  };

  try {
    const res = await fetch('/api/v1/plans/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.message || 'Generation failed');
    currentPlan = data;
    renderResult(data);
    document.getElementById('result-panel').classList.remove('hidden');
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Generate Plan</span>';
  }
}

// ─── Render Result ──────────────────────────────────────────────────────────
function renderResult(data) {
  const plan = data.plan;
  document.getElementById('result-title').textContent =
    `${plan.role_display} → ${plan.destination_display}`;
  document.getElementById('result-subtitle').textContent =
    `Generated ${new Date(data.generated_at).toLocaleString()}`;

  const badge = document.getElementById('feasibility-badge');
  badge.textContent = plan.feasibility_score.replace('_', ' ');
  badge.className = `feasibility-badge badge-${plan.feasibility_score}`;

  renderOverview(plan);
  renderVisa(plan);
  renderActions(plan);
  renderNarrative(plan);
  switchResultTab('overview');
}

function renderOverview(plan) {
  const sa = plan.salary_analysis;
  const ta = plan.timeline_analysis;
  const warns = plan.warnings || [];

  const warnHtml = warns.map(w =>
    `<div class="warn-item warn-${w.severity}">
      <span>${w.severity === 'critical' ? '🚨' : w.severity === 'warning' ? '⚠️' : 'ℹ️'}</span>
      <span>${w.message}</span>
    </div>`
  ).join('');

  document.getElementById('result-overview').innerHTML = `
    <div class="overview-grid">
      <div class="stat-card">
        <div class="stat-label">Your Salary Expectation</div>
        <div class="stat-value">${sa.currency_code} ${sa.user_expectation.toLocaleString()}</div>
        <div class="stat-sub">Market: ${sa.currency_code} ${sa.market_min.toLocaleString()} – ${sa.currency_code} ${sa.market_max.toLocaleString()}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Timeline Feasibility</div>
        <div class="stat-value">${ta.is_feasible ? '✅ Feasible' : '❌ Tight'}</div>
        <div class="stat-sub">You: ${ta.user_timeline_months}mo · Est: ${ta.estimated_min_months}–${ta.estimated_max_months}mo</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Market Demand</div>
        <div class="stat-value" style="text-transform:capitalize">${plan.market_demand_level}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Salary Position</div>
        <div class="stat-value">${sa.is_within_market_range ? '✅ In range' : '⚠️ Out of range'}</div>
        <div class="stat-sub">${sa.percentile_estimate}</div>
      </div>
    </div>
    ${warns.length ? `<div class="warnings-box">${warnHtml}</div>` : ''}
  `;
}

function renderVisa(plan) {
  const routes = plan.visa_routes || [];
  document.getElementById('result-visa').innerHTML = `
    <div class="visa-list">
      ${routes.map(r => `
        <div class="visa-card">
          <div class="visa-card-header">
            <h4>${r.name}</h4>
            <span class="${r.is_eligible ? 'eligible-yes' : 'eligible-no'}">
              ${r.is_eligible ? '✅ Eligible' : '❌ Not Eligible'}
            </span>
          </div>
          <div class="visa-meta">
            Type: ${r.type} · Processing: ${r.processing_time_months.min}–${r.processing_time_months.max} months
            ${r.salary_threshold ? ` · Salary min: ${r.salary_threshold.toLocaleString()}` : ''}
          </div>
          <ul class="visa-reasons">${(r.reasons || []).map(x => `<li>${x}</li>`).join('')}</ul>
        </div>
      `).join('')}
    </div>
  `;
}

function renderActions(plan) {
  const steps = plan.action_steps || [];
  document.getElementById('result-action').innerHTML = `
    <div class="action-list">
      ${steps.map(s => `
        <div class="action-step">
          <div class="step-num">${s.order}</div>
          <div class="step-body">
            <h4>${s.title}</h4>
            <p>${s.description}</p>
            ${s.estimated_duration ? `<div class="step-dur">⏱ ${s.estimated_duration}</div>` : ''}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderNarrative(plan) {
  const meta = plan.llm_metadata || {};
  document.getElementById('result-narrative').innerHTML = plan.narrative
    ? `<div class="narrative-box">${plan.narrative}</div>
       <div class="narrative-meta">Model: ${meta.model || 'N/A'} · Latency: ${meta.latency_ms || '?'}ms</div>`
    : `<div class="narrative-box" style="color:var(--muted)">No AI narrative available. ${meta.error || 'LLM may not be configured.'}</div>`;
}

function switchResultTab(name) {
  ['overview', 'visa', 'action', 'narrative'].forEach(t => {
    document.getElementById(`result-${t}`).classList.toggle('hidden', t !== name);
  });
  document.querySelectorAll('.rtab').forEach((el, i) => {
    el.classList.toggle('active', ['overview', 'visa', 'action', 'narrative'][i] === name);
  });
}

// ─── Save Plan ─────────────────────────────────────────────────────────────
async function savePlan() {
  if (!currentPlan) return;
  const msgEl = document.getElementById('save-msg');
  msgEl.className = 'save-msg hidden';

  try {
    const res = await fetch('/api/v1/plans/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      body: JSON.stringify({
        plan: currentPlan.plan,
        input_summary: currentPlan.input_summary,
        title: document.getElementById('save-title').value || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Save failed');
    msgEl.textContent = `✅ Saved as "${data.title}"`;
    msgEl.className = 'save-msg save-success';
  } catch (err) {
    msgEl.textContent = `❌ ${err.message}`;
    msgEl.className = 'save-msg save-error';
  }
  msgEl.classList.remove('hidden');
  setTimeout(() => msgEl.classList.add('hidden'), 4000);
}

// ─── Saved Plans ────────────────────────────────────────────────────────────
async function loadSavedPlans() {
  const container = document.getElementById('saved-list');
  container.innerHTML = '<div class="loading-msg">Loading...</div>';
  try {
    const res = await fetch('/api/v1/plans', { headers: authHeader() });
    const data = await res.json();
    if (!data.length) {
      container.innerHTML = '<div class="empty-msg">No saved plans yet. Generate one first!</div>';
      return;
    }
    container.innerHTML = data.map(p => `
      <div class="saved-card" onclick="viewSavedPlan(${p.id})">
        <div>
          <h4>${p.title}</h4>
          <p>${formatSlug(p.role)} → ${formatSlug(p.destination)} · ${new Date(p.created_at).toLocaleDateString()}</p>
        </div>
        <span class="saved-card-arrow">→</span>
      </div>
    `).join('');
  } catch {
    container.innerHTML = '<div class="empty-msg">Failed to load plans.</div>';
  }
}

async function viewSavedPlan(id) {
  try {
    const res = await fetch(`/api/v1/plans/${id}`, { headers: authHeader() });
    const saved = await res.json();
    currentPlan = { plan: saved.result, input_summary: saved.input_snapshot, generated_at: saved.created_at };
    renderResult(currentPlan);
    showSection('generate');
    document.getElementById('result-panel').classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch { alert('Failed to load plan detail.'); }
}
