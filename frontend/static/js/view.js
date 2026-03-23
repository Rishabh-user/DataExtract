let docData = null;

async function loadDocument() {
  try {
    docData = await apiFetch(`/api/document/${DOC_ID}`);

    // Header
    document.getElementById('docFileName').textContent = docData.file_name;
    document.getElementById('docType').textContent     = docData.file_type;
    document.getElementById('docSource').textContent   = docData.source || '—';
    document.getElementById('docDate').textContent     = fmtDate(docData.upload_date);
    document.getElementById('docSize').textContent     = fmtBytes(docData.file_size_bytes);
    document.getElementById('docStatus').innerHTML     = badge(docData.status);

    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('docHeader').classList.remove('hidden');
    document.getElementById('docTabs').classList.remove('hidden');
    document.getElementById('emailBtn').style.display = '';

    renderContent();
    renderMetadata();
    renderRaw();

  } catch (err) {
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('errorState').classList.remove('hidden');
    if (err.status === 401) {
      document.getElementById('errorMsg').textContent =
        ApiKey.get()
          ? 'Invalid or revoked API key. Click the key in the sidebar to update it.'
          : 'API key required. Click the key area in the sidebar to set one.';
      if (!ApiKey.get()) openApiKeyModal();
    } else if (err.status === 403) {
      document.getElementById('errorMsg').textContent =
        'Your API key does not have "view" permission for this document.';
    } else {
      document.getElementById('errorMsg').textContent = err.message;
    }
  }
}

function renderContent() {
  const container = document.getElementById('pagesContainer');
  if (!docData.pages.length) {
    container.innerHTML = '<div class="card empty-state"><div class="empty-icon">📄</div><p>No content was extracted.</p></div>';
    return;
  }
  container.innerHTML = docData.pages.map(page => `
    <div class="page-block card" style="padding:0;overflow:hidden;margin-bottom:16px">
      <div class="page-header">
        <span>${docData.file_type === '.xlsx' || docData.file_type === '.xls'
          ? `📊 Sheet ${page.page_number}${page.metadata?.sheet_name ? ' — ' + escapeHtml(page.metadata.sheet_name) : ''}`
          : docData.file_type === '.pptx' ? `📑 Slide ${page.page_number}`
          : `📄 Page ${page.page_number}`
        }</span>
        <span class="text-muted text-xs">${page.content ? page.content.length + ' chars' : 'empty'}</span>
      </div>
      <div style="padding:16px">
        <div class="content-block">${escapeHtml(page.content || '(empty)')}</div>
        ${page.metadata && Object.keys(page.metadata).length ? `
          <details class="mt-1">
            <summary class="text-muted text-sm" style="cursor:pointer">🔍 Page metadata</summary>
            <div class="content-block mt-1" style="max-height:200px">${escapeHtml(JSON.stringify(page.metadata, null, 2))}</div>
          </details>` : ''}
      </div>
    </div>`).join('');
}

function renderMetadata() {
  const fields = [
    ['Project',    docData.project_name || '—'],
    ['File Name',  docData.file_name],
    ['File Type',  docData.file_type],
    ['Source',     docData.source || '—'],
    ['Status',     docData.status],
    ['Upload Date',fmtDate(docData.upload_date)],
    ['File Size',  fmtBytes(docData.file_size_bytes)],
    ['Pages',      docData.pages.length],
    ['Document ID',docData.id],
  ];
  document.getElementById('metadataContainer').innerHTML = `
    <table>
      <thead><tr><th>Field</th><th>Value</th></tr></thead>
      <tbody>${fields.map(([k,v]) => `<tr><td class="fw-600 text-sm">${k}</td><td>${escapeHtml(String(v))}</td></tr>`).join('')}</tbody>
    </table>`;
}

function renderRaw() {
  const el = document.getElementById('rawJson');
  el.textContent = JSON.stringify(docData, null, 2);
  el.dataset.raw = el.textContent;
}

function copyRaw() {
  const btn = document.querySelector('#tab-raw .btn');
  copyText(document.getElementById('rawJson').dataset.raw || '', btn);
}

function switchTab(name, el) {
  ['content','metadata','raw'].forEach(t => {
    document.getElementById(`tab-${t}`).classList.toggle('hidden', t !== name);
  });
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

// Email modal
function openEmailModal() {
  Modal.show('emailModal');
}

async function sendEmail() {
  const to = document.getElementById('emailTo').value.trim();
  if (!to) { Toast.error('Enter a recipient email.'); return; }
  try {
    const result = await apiFetch('/api/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to, template: 'extraction_summary', document_id: DOC_ID }),
    });
    Modal.hide('emailModal');
    Toast.success(result.message);
  } catch (e) {
    Toast.error(e.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!ApiKey.get()) { openApiKeyModal(); }
  else loadDocument();
});
