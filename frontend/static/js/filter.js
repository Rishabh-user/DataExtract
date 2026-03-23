let currentMode = 'filter';
let currentPage = 1;
let pageSize    = 20;

function setMode(mode, el) {
  currentMode = mode;
  document.getElementById('filterPanel').classList.toggle('hidden', mode !== 'filter');
  document.getElementById('searchPanel').classList.toggle('hidden', mode !== 'search');
  document.querySelectorAll('#modeTabs .tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  clearResults();
}

function clearFilters() {
  ['filterType','filterStatus','filterSource','dateFrom','dateTo'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
}

function clearResults() {
  document.getElementById('resultsBody').innerHTML =
    '<tr><td colspan="8" class="text-center text-muted" style="padding:32px">Use filters above to load documents.</td></tr>';
  document.getElementById('searchResultsContainer').classList.add('hidden');
  document.getElementById('tableWrap').classList.remove('hidden');
  document.getElementById('pagination').innerHTML = '';
  document.getElementById('resultsMeta').textContent = '';
}

function changePageSize(val) {
  pageSize = parseInt(val);
  currentPage = 1;
  if (currentMode === 'filter') runFilter();
}

async function runFilter() {
  if (!ApiKey.get()) { openApiKeyModal(); return; }

  const params = new URLSearchParams({ page: currentPage, size: pageSize });
  const type   = document.getElementById('filterType').value;
  const source = document.getElementById('filterSource').value.trim();
  const status = document.getElementById('filterStatus').value;
  const from   = document.getElementById('dateFrom').value;
  const to     = document.getElementById('dateTo').value;
  if (type)   params.set('file_type', type);
  if (source) params.set('source', source);
  if (status) params.set('status', status);
  if (from)   params.set('date_from', from);
  if (to)     params.set('date_to', to);

  setLoading(true);
  document.getElementById('searchResultsContainer').classList.add('hidden');
  document.getElementById('tableWrap').classList.remove('hidden');

  try {
    const data = await apiFetch(`/api/filter?${params}`);
    renderTable(data.results, data.total, data.page, data.size);
  } catch (e) {
    Toast.error(e.message);
    if (e.status === 401) openApiKeyModal();
  } finally {
    setLoading(false);
  }
}

async function runSearch() {
  if (!ApiKey.get()) { openApiKeyModal(); return; }
  const q = document.getElementById('searchQuery').value.trim();
  if (!q) { Toast.warn('Enter a search query.'); return; }

  const params = new URLSearchParams({ q, page: currentPage, size: pageSize });
  const type   = document.getElementById('searchType').value;
  const source = document.getElementById('searchSource').value.trim();
  if (type)   params.set('file_type', type);
  if (source) params.set('source', source);

  setLoading(true);
  document.getElementById('tableWrap').classList.add('hidden');
  document.getElementById('searchResultsContainer').classList.remove('hidden');

  try {
    const data = await apiFetch(`/api/search?${params}`);
    renderSearchResults(data);
  } catch (e) {
    Toast.error(e.message);
    if (e.status === 401) openApiKeyModal();
  } finally {
    setLoading(false);
  }
}

function renderTable(results, total, page, size) {
  document.getElementById('resultsTitle').textContent = 'Documents';
  document.getElementById('resultsMeta').textContent =
    `${total} total · page ${page} of ${Math.ceil(total / size) || 1}`;

  if (!results.length) {
    document.getElementById('resultsBody').innerHTML =
      '<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">📂</div><p>No documents match your filters.</p></div></td></tr>';
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  document.getElementById('resultsBody').innerHTML = results.map(d => `<tr>
    <td class="text-muted text-sm">${d.id}</td>
    <td><a href="/view/${d.id}" class="truncate" style="display:inline-block;max-width:220px" title="${escapeHtml(d.file_name)}">${escapeHtml(d.file_name)}</a></td>
    <td><span class="badge badge-info font-mono">${escapeHtml(d.file_type)}</span></td>
    <td class="text-muted text-sm">${escapeHtml(d.source || '—')}</td>
    <td class="text-muted text-sm">${fmtBytes(d.file_size_bytes)}</td>
    <td class="text-muted text-sm">${fmtDate(d.upload_date)}</td>
    <td>${badge(d.status)}</td>
    <td>
      <a href="/view/${d.id}" class="btn btn-primary btn-sm">View</a>
    </td>
  </tr>`).join('');

  renderPagination(total, page, size, (p) => { currentPage = p; runFilter(); });
}

function renderSearchResults(data) {
  const container = document.getElementById('searchResultsContainer');
  document.getElementById('resultsTitle').textContent = `Search: "${data.query}"`;
  document.getElementById('resultsMeta').textContent  = `${data.total} result${data.total !== 1 ? 's' : ''}`;

  if (!data.results.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">🔍</div><p>No results found.</p></div>';
    return;
  }

  container.innerHTML = data.results.map(h => `
    <div class="card" style="margin-bottom:12px;padding:16px">
      <div class="flex-between" style="flex-wrap:wrap;gap:6px;margin-bottom:8px">
        <a href="/view/${h.document_id}" style="font-weight:600;text-decoration:none">${escapeHtml(h.file_name)}</a>
        <div style="display:flex;gap:6px;align-items:center">
          <span class="badge badge-info font-mono">${escapeHtml(h.file_type)}</span>
          ${h.source ? `<span class="badge badge-primary">${escapeHtml(h.source)}</span>` : ''}
          ${h.page_number ? `<span class="text-muted text-xs">Page ${h.page_number}</span>` : ''}
          ${h.score ? `<span class="text-muted text-xs">Score: ${h.score.toFixed(2)}</span>` : ''}
        </div>
      </div>
      <div class="content-block" style="max-height:120px">${escapeHtml(h.content_snippet)}</div>
      <a href="/view/${h.document_id}" class="btn btn-primary btn-sm mt-1">View Document →</a>
    </div>`).join('');

  renderPagination(data.total, data.page, data.size, (p) => { currentPage = p; runSearch(); });
}

function renderPagination(total, page, size, onPage) {
  const pages = Math.ceil(total / size);
  if (pages <= 1) { document.getElementById('pagination').innerHTML = ''; return; }

  let html = `<button class="page-btn" onclick="(${onPage})(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`;
  const start = Math.max(1, page - 2);
  const end   = Math.min(pages, page + 2);
  if (start > 1) html += `<button class="page-btn" onclick="(${onPage})(1)">1</button>${start > 2 ? '<span style="padding:0 4px" class="text-muted">…</span>' : ''}`;
  for (let p = start; p <= end; p++) {
    html += `<button class="page-btn ${p === page ? 'active' : ''}" onclick="(${onPage})(${p})">${p}</button>`;
  }
  if (end < pages) html += `${end < pages - 1 ? '<span style="padding:0 4px" class="text-muted">…</span>' : ''}<button class="page-btn" onclick="(${onPage})(${pages})">${pages}</button>`;
  html += `<button class="page-btn" onclick="(${onPage})(${page + 1})" ${page >= pages ? 'disabled' : ''}>›</button>`;
  document.getElementById('pagination').innerHTML = html;
}

function setLoading(on) {
  document.getElementById('loadingRow').classList.toggle('hidden', !on);
}

document.addEventListener('DOMContentLoaded', () => {
  if (ApiKey.get()) runFilter();
  else {
    document.getElementById('resultsBody').innerHTML =
      '<tr><td colspan="8" class="text-center text-muted" style="padding:32px">Set an API key in the sidebar, then click <strong>Apply Filters</strong>.</td></tr>';
  }
});
