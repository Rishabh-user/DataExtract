function onTemplateChange() {
  const tpl = document.getElementById('templateSelect').value;
  document.getElementById('fieldDocumentId').classList.toggle('hidden', tpl !== 'extraction_summary');
  document.getElementById('fieldApiKey').classList.toggle('hidden', tpl !== 'api_key_created');
}

async function sendEmail() {
  const to  = document.getElementById('emailTo').value.trim();
  const tpl = document.getElementById('templateSelect').value;
  if (!to) { Toast.error('Recipient email is required.'); return; }

  const payload = { to, template: tpl };
  if (tpl === 'extraction_summary') {
    const docId = document.getElementById('docIdInput').value.trim();
    if (!docId) { Toast.error('Document ID is required for this template.'); return; }
    payload.document_id = parseInt(docId);
  }
  if (tpl === 'api_key_created') {
    payload.project_name    = document.getElementById('projectNameInput').value.trim();
    payload.api_key_preview = document.getElementById('apiKeyPreviewInput').value.trim();
    if (!payload.project_name || !payload.api_key_preview) {
      Toast.error('Project name and API key are required for this template.'); return;
    }
  }

  const btn = document.querySelector('button[onclick="sendEmail()"]');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Sending…';

  try {
    const result = await apiFetch('/api/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const el = document.getElementById('sendResult');
    el.innerHTML = `<div class="alert alert-success">
      ✅ ${escapeHtml(result.message)}
      ${result.backend === 'dummy' ? '<br><span class="text-sm">Email saved to <code>email_logs/</code> — open the HTML file to preview it.</span>' : ''}
    </div>`;
    el.classList.remove('hidden');
    Toast.success('Email sent (dummy mode)!');
    loadLogs();
  } catch (e) {
    const el = document.getElementById('sendResult');
    el.innerHTML = `<div class="alert alert-error">✕ ${escapeHtml(e.message)}</div>`;
    el.classList.remove('hidden');
    Toast.error(e.message);
    if (e.status === 401) openApiKeyModal();
  } finally {
    btn.disabled = false;
    btn.innerHTML = '📧 Send Email';
  }
}

async function loadLogs() {
  // List email log files via a small admin trick — just show a hint since
  // we can't list the filesystem from the browser directly
  const el = document.getElementById('logList');
  el.innerHTML = `<div class="alert alert-info text-sm">
    Email logs are saved to <code>email_logs/</code> in your project root.
    Open any <code>.html</code> file in your browser to preview the rendered email.
  </div>`;
}

document.addEventListener('DOMContentLoaded', () => {
  onTemplateChange();
});
