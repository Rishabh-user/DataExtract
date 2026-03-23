/**
 * DataExtract — Shared App Utilities
 * Handles: API key management (localStorage), toast notifications,
 * modal helpers, and common fetch wrapper.
 */

const LS_KEY = 'dataextract_api_key';

/* ─── API Key ─────────────────────────────────────────────────── */
const ApiKey = {
  get()    { return localStorage.getItem(LS_KEY) || ''; },
  set(key) { localStorage.setItem(LS_KEY, key); ApiKey._refresh(); },
  clear()  { localStorage.removeItem(LS_KEY); ApiKey._refresh(); },
  _refresh() {
    const el = document.getElementById('sidebar-key-value');
    const none = document.getElementById('sidebar-key-none');
    const adminBar = document.getElementById('admin-session-bar');
    const key = ApiKey.get();
    if (el)   el.textContent = key ? key.slice(0, 8) + '…' + key.slice(-4) : '';
    if (none) none.classList.toggle('hidden', !!key);
    if (el)   el.parentElement.classList.toggle('hidden', !key);
    if (adminBar) adminBar.classList.toggle('hidden', !key);
  },
};

/* ─── API fetch wrapper ───────────────────────────────────────── */
async function apiFetch(url, opts = {}) {
  const key = ApiKey.get();
  const headers = { ...opts.headers };
  if (key) headers['x-api-key'] = key;
  const resp = await fetch(url, { ...opts, headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = data.error || data.detail || `HTTP ${resp.status}`;
    throw Object.assign(new Error(msg), { status: resp.status, data });
  }
  return data;
}

/* ─── Toast ───────────────────────────────────────────────────── */
const Toast = (() => {
  let container;
  function init() {
    if (container) return;
    container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }
  }
  function show(msg, type = 'info', duration = 4000) {
    init();
    const icons = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
    t.onclick = () => t.remove();
    container.appendChild(t);
    setTimeout(() => t.classList.add('hidden'), duration - 300);
    setTimeout(() => t.remove(), duration);
  }
  return {
    success: (m, d) => show(m, 'success', d),
    error:   (m, d) => show(m, 'error', d),
    info:    (m, d) => show(m, 'info', d),
    warn:    (m, d) => show(m, 'warn', d),
  };
})();

/* ─── Modal helpers ───────────────────────────────────────────── */
const Modal = {
  show(id)  { document.getElementById(id)?.classList.remove('hidden'); },
  hide(id)  { document.getElementById(id)?.classList.add('hidden'); },
  toggle(id){ document.getElementById(id)?.classList.toggle('hidden'); },
};

/* ─── Copy to clipboard ───────────────────────────────────────── */
async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const orig = btn.textContent;
    btn.textContent = '✓ Copied';
    setTimeout(() => btn.textContent = orig, 1800);
  } catch {
    Toast.warn('Could not copy — please select and copy manually.');
  }
}

/* ─── Format helpers ──────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
function fmtBytes(n) {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n/1024).toFixed(1)} KB`;
  return `${(n/1048576).toFixed(2)} MB`;
}
function badge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}
function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

/* ─── Checkbox group helper ────────────────────────────────────── */
function initCheckboxGroup(containerId) {
  document.querySelectorAll(`#${containerId} .checkbox-item`).forEach(item => {
    const cb = item.querySelector('input[type=checkbox]');
    item.classList.toggle('checked', cb.checked);
    // Use 'change' on the checkbox itself — avoids the double-toggle that
    // happens when listening to 'click' on the wrapping label (browser also
    // fires a synthetic click on the input, toggling it a second time).
    cb.addEventListener('change', () => {
      item.classList.toggle('checked', cb.checked);
    });
  });
}
function getCheckedValues(containerId) {
  return [...document.querySelectorAll(`#${containerId} .checkbox-item input:checked`)]
    .map(cb => cb.value);
}

/* ─── API Key Modal ───────────────────────────────────────────── */
function openApiKeyModal() {
  const overlay = document.getElementById('api-key-modal');
  if (!overlay) return;
  document.getElementById('modal-key-input').value = ApiKey.get();
  Modal.show('api-key-modal');
}
function closeApiKeyModal() { Modal.hide('api-key-modal'); }

function saveApiKeyFromModal() {
  const val = document.getElementById('modal-key-input').value.trim();
  if (!val) { Toast.error('Please enter an API key.'); return; }
  ApiKey.set(val);
  Toast.success('API key saved.');
  closeApiKeyModal();
}

/* ─── Init on DOMContentLoaded ────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  ApiKey._refresh();

  // Highlight active nav item
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(a => {
    const href = a.getAttribute('href');
    a.classList.toggle('active',
      href === path || (href !== '/' && path.startsWith(href))
    );
  });

  // Sidebar key click → open modal
  document.getElementById('sidebar-key-area')?.addEventListener('click', openApiKeyModal);

  // Close modal on overlay click
  document.getElementById('api-key-modal')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) closeApiKeyModal();
  });

  // Show key prompt on first visit if no key stored
  if (!ApiKey.get() && document.getElementById('api-key-modal')) {
    setTimeout(() => {
      Modal.show('api-key-modal');
    }, 600);
  }
});
