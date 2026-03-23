document.addEventListener('DOMContentLoaded', () => {
  initCheckboxGroup('genActions');
  initCheckboxGroup('genFileTypes');
  loadKeys();
});

async function loadKeys() {
  document.getElementById('keysLoading').classList.remove('hidden');
  document.getElementById('keysTable').classList.add('hidden');
  document.getElementById('keysEmpty').classList.add('hidden');

  try {
    const keys = await apiFetch('/api/auth/keys');
    renderKeys(keys);
  } catch (e) {
    Toast.error(e.message);
    if (e.status === 401) openApiKeyModal();
    document.getElementById('keysLoading').classList.add('hidden');
  }
}

function renderKeys(keys) {
  document.getElementById('keysLoading').classList.add('hidden');
  if (!keys.length) {
    document.getElementById('keysEmpty').classList.remove('hidden');
    return;
  }

  document.getElementById('keysTable').classList.remove('hidden');
  document.getElementById('keysBody').innerHTML = keys.map(k => {
    const perms   = k.permissions || {};
    const actions = (perms.actions || []).join(', ') || '—';
    const types   = (perms.file_types || []).join(', ') || '—';
    return `<tr>
      <td class="text-muted text-sm">${k.id}</td>
      <td><strong>${escapeHtml(k.project_name)}</strong></td>
      <td class="text-sm">${escapeHtml(actions)}</td>
      <td class="font-mono text-sm">${escapeHtml(types === '*' ? 'All types' : types)}</td>
      <td class="text-muted text-sm">${fmtDate(k.created_at)}</td>
      <td>${badge(k.status === 'active' ? 'active' : 'revoked')}</td>
      <td style="text-align:right">
        <div style="display:flex;gap:6px;justify-content:flex-end">
          <button class="btn btn-outline btn-sm" onclick="openEdit(${JSON.stringify(k).replace(/"/g,'&quot;')})">✏️ Edit</button>
          ${k.status === 'active'
            ? `<button class="btn btn-danger btn-sm" onclick="revokeKey(${k.id})">Revoke</button>`
            : `<button class="btn btn-success btn-sm" onclick="reactivateKey(${k.id})">Reactivate</button>`}
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── Generate Key ────────────────────────────────────────────────
function toggleAllTypes(cb) {
  const items = document.querySelectorAll('#genFileTypes .checkbox-item');
  items.forEach(item => {
    const input = item.querySelector('input');
    input.checked = false;
    item.classList.remove('checked');
    item.style.opacity = cb.checked ? '0.4' : '1';
    item.style.pointerEvents = cb.checked ? 'none' : '';
  });
  document.getElementById('allTypesToggle').classList.toggle('checked', cb.checked);
}

async function generateKey() {
  const project = document.getElementById('genProjectName').value.trim();
  if (!project) { Toast.error('Project name is required.'); return; }

  const actions = getCheckedValues('genActions');
  if (!actions.length) { Toast.error('Select at least one action.'); return; }

  const allTypes = document.getElementById('allTypesCheck').checked;
  const fileTypes = allTypes ? ['*'] : getCheckedValues('genFileTypes');
  if (!allTypes && !fileTypes.length) { Toast.error('Select at least one file type, or enable All Types.'); return; }

  const dbUrl = document.getElementById('genDbUrl')?.value.trim() || null;
  const emailTo = document.getElementById('genEmailTo').value.trim();

  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating…';

  try {
    const payload = { project_name: project, allowed_actions: actions, allowed_file_types: fileTypes };
    if (dbUrl) payload.db_url = dbUrl;

    const data = await fetch('/api/auth/generate-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => r.json());

    if (data.error) throw new Error(data.error);

    Modal.hide('generateModal');

    // Auto-save key so all pages work immediately
    ApiKey.set(data.api_key);

    // Show reveal modal
    document.getElementById('revealKeyText').textContent = data.api_key;
    document.getElementById('revealKey').dataset.key     = data.api_key;
    document.getElementById('revealProject').textContent = data.project_name;
    Modal.show('revealModal');

    // Optionally send email
    if (emailTo) {
      const perms = data.permissions || {};
      apiFetch('/api/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: emailTo,
          template: 'api_key_created',
          project_name: data.project_name,
          api_key_preview: data.api_key,
        }),
      }).then(() => Toast.info(`Key also emailed to ${emailTo}`)).catch(() => {});
    }

    loadKeys();
    Toast.success(`Key generated for "${project}"`);

    // Reset form
    document.getElementById('genProjectName').value = '';
    if (document.getElementById('genDbUrl')) document.getElementById('genDbUrl').value = '';
    document.getElementById('genEmailTo').value = '';

  } catch (e) {
    Toast.error(e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Generate Key';
  }
}

function useThisKey() {
  const key = document.getElementById('revealKey').dataset.key;
  if (key) {
    ApiKey.set(key);
    Toast.success('Key is active in sidebar.');
  }
}

// ── Edit Key ────────────────────────────────────────────────────
function openEdit(key) {
  document.getElementById('editKeyId').value         = key.id;
  document.getElementById('editProjectName').value   = key.project_name;
  document.getElementById('editStatus').value        = key.status;

  const perms     = key.permissions || {};
  const actions   = perms.actions   || ['upload','view','filter','search'];
  const fileTypes = perms.file_types || ['*'];
  const allTypes  = fileTypes.includes('*');

  // Actions
  document.querySelectorAll('#editActions .checkbox-item').forEach(item => {
    const cb = item.querySelector('input');
    cb.checked = actions.includes(cb.value);
    item.classList.toggle('checked', cb.checked);
  });
  initCheckboxGroup('editActions');

  // File types
  document.getElementById('editAllTypesCheck').checked = allTypes;
  document.getElementById('editAllTypesToggle').classList.toggle('checked', allTypes);
  document.querySelectorAll('#editFileTypes .checkbox-item').forEach(item => {
    const cb = item.querySelector('input');
    cb.checked = !allTypes && fileTypes.includes(cb.value);
    item.classList.toggle('checked', cb.checked);
    item.style.opacity = allTypes ? '0.4' : '1';
    item.style.pointerEvents = allTypes ? 'none' : '';
  });
  initCheckboxGroup('editFileTypes');

  Modal.show('editModal');
}

function toggleEditAllTypes(cb) {
  const items = document.querySelectorAll('#editFileTypes .checkbox-item');
  items.forEach(item => {
    const input = item.querySelector('input');
    input.checked = false;
    item.classList.remove('checked');
    item.style.opacity = cb.checked ? '0.4' : '1';
    item.style.pointerEvents = cb.checked ? 'none' : '';
  });
  document.getElementById('editAllTypesToggle').classList.toggle('checked', cb.checked);
}

async function saveEdit() {
  const id      = document.getElementById('editKeyId').value;
  const actions = getCheckedValues('editActions');
  const allTypes= document.getElementById('editAllTypesCheck').checked;
  const types   = allTypes ? ['*'] : getCheckedValues('editFileTypes');
  const status  = document.getElementById('editStatus').value;

  if (!actions.length) { Toast.error('Select at least one action.'); return; }
  if (!allTypes && !types.length) { Toast.error('Select at least one file type.'); return; }

  try {
    await apiFetch(`/api/auth/keys/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ allowed_actions: actions, allowed_file_types: types, status }),
    });
    Modal.hide('editModal');
    Toast.success('Permissions updated.');
    loadKeys();
  } catch (e) {
    Toast.error(e.message);
  }
}

async function revokeKey(id) {
  if (!confirm('Revoke this API key? It will immediately stop working.')) return;
  try {
    await apiFetch(`/api/auth/keys/${id}`, {
      method: 'DELETE',
    });
    Toast.success('Key revoked.');
    loadKeys();
  } catch (e) {
    Toast.error(e.message);
  }
}

async function reactivateKey(id) {
  try {
    await apiFetch(`/api/auth/keys/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'active' }),
    });
    Toast.success('Key reactivated.');
    loadKeys();
  } catch (e) {
    Toast.error(e.message);
  }
}
