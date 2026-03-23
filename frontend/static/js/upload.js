const dropZone  = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileInfo  = document.getElementById('fileInfo');
const uploadBtn = document.getElementById('uploadBtn');
const resultDiv = document.getElementById('uploadResult');
let selectedFile = null;

// Drag & drop
dropZone.addEventListener('click',     () => fileInput.click());
dropZone.addEventListener('dragover',  e  => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop',      e  => {
  e.preventDefault(); dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) handleFile(fileInput.files[0]); });

function handleFile(file) {
  selectedFile = file;
  fileInfo.innerHTML = `📄 <strong>${escapeHtml(file.name)}</strong> &nbsp;(${fmtBytes(file.size)})`;
  fileInfo.classList.remove('hidden');
  uploadBtn.disabled = false;
}

uploadBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  if (!ApiKey.get()) { openApiKeyModal(); return; }

  uploadBtn.disabled = true;
  uploadBtn.innerHTML = '<span class="spinner"></span> Extracting…';
  resultDiv.classList.add('hidden');

  // Show progress bar
  const prog    = document.getElementById('uploadProgress');
  const bar     = document.getElementById('progressBar');
  const pctLbl  = document.getElementById('progressPct');
  const stepLbl = document.getElementById('progressLabel');
  prog.classList.remove('hidden');

  // Animate progress (simulated — real progress not available via fetch)
  let pct = 0;
  const ticker = setInterval(() => {
    pct = Math.min(pct + Math.random() * 8, 85);
    bar.style.width   = pct + '%';
    pctLbl.textContent = Math.round(pct) + '%';
    stepLbl.textContent = pct < 30 ? 'Uploading…' : pct < 60 ? 'Extracting content…' : 'Saving to database…';
  }, 300);

  try {
    const formData = new FormData();
    formData.append('file', selectedFile);
    const src = document.getElementById('source').value.trim();
    if (src) formData.append('source', src);

    const data = await apiFetch('/api/upload', { method: 'POST', body: formData });

    clearInterval(ticker);
    bar.style.width = '100%'; bar.classList.add('progress-success');
    pctLbl.textContent = '100%'; stepLbl.textContent = 'Done!';

    resultDiv.innerHTML = `<div class="alert alert-success">
      ✅ <strong>${escapeHtml(data.file_name)}</strong> extracted successfully.
      Status: ${badge(data.status)} &nbsp; ID: <strong>#${data.id}</strong>
      ${data.project_name ? `&nbsp; Project: <strong>${escapeHtml(data.project_name)}</strong>` : ''}
      <div class="mt-1">
        <a href="/view/${data.id}" class="btn btn-primary btn-sm">View Extracted Data →</a>
      </div>
    </div>`;
    resultDiv.classList.remove('hidden');
    Toast.success(`${data.file_name} extracted!`);

    // Reset form after 2s
    setTimeout(() => { prog.classList.add('hidden'); bar.style.width = '0%'; bar.classList.remove('progress-success'); }, 2000);

  } catch (err) {
    clearInterval(ticker);
    prog.classList.add('hidden');
    const msg = err.message || 'Upload failed.';
    resultDiv.innerHTML = `<div class="alert alert-error">✕ ${escapeHtml(msg)}</div>`;
    resultDiv.classList.remove('hidden');
    Toast.error(msg);
    if (err.status === 403) Toast.warn('Check your API key permissions for this file type.');
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = '📤 Upload &amp; Extract';
  }
});
