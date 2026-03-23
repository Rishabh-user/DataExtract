let currentPage = 1;
const pageSize  = 50;

async function loadTable(page) {
  currentPage = page;
  const table = document.getElementById('tableSelect').value;

  document.getElementById('dbLoading').classList.remove('hidden');
  document.getElementById('dbTable').classList.add('hidden');
  document.getElementById('dbEmpty').classList.add('hidden');
  document.getElementById('tableStats').classList.add('hidden');
  document.getElementById('dbPagination').innerHTML = '';

  try {
    const data = await apiFetch(`/api/admin/db/${table}?page=${page}&size=${pageSize}`);

    document.getElementById('dbLoading').classList.add('hidden');

    if (!data.rows.length) {
      document.getElementById('dbEmpty').classList.remove('hidden');
      return;
    }

    // Stats bar
    document.getElementById('statTable').textContent = data.table;
    document.getElementById('statTotal').textContent = data.total;
    document.getElementById('statPage').textContent  = data.page;
    document.getElementById('statPages').textContent = Math.ceil(data.total / pageSize);
    document.getElementById('tableStats').classList.remove('hidden');

    // Table head
    document.getElementById('dbHead').innerHTML =
      `<tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;

    // Table body — truncate long values
    document.getElementById('dbBody').innerHTML = data.rows.map(row =>
      `<tr>${row.map((cell, i) => {
        const col = data.columns[i];
        let display = cell === null || cell === undefined ? '<span class="text-muted">null</span>' : escapeHtml(String(cell));
        // Truncate long content cells
        if (col === 'content' && String(cell).length > 120) {
          display = `<span title="${escapeHtml(String(cell))}">${escapeHtml(String(cell).slice(0, 120))}…</span>`;
        }
        // Mask api_key column
        if (col === 'api_key' && cell) {
          display = `<span class="font-mono text-muted">${escapeHtml(String(cell).slice(0, 8))}…${escapeHtml(String(cell).slice(-4))}</span>`;
        }
        // Pretty-print JSON
        if ((col === 'metadata' || col === 'permissions') && cell) {
          try {
            const parsed = typeof cell === 'string' ? JSON.parse(cell) : cell;
            display = `<details><summary class="text-muted text-xs" style="cursor:pointer">JSON</summary><pre style="font-size:0.72rem;white-space:pre-wrap;max-width:300px">${escapeHtml(JSON.stringify(parsed, null, 2))}</pre></details>`;
          } catch {}
        }
        const isNum = typeof cell === 'number';
        return `<td class="${isNum ? 'text-sm' : ''}" style="${col === 'file_path' ? 'max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' : ''}">${display}</td>`;
      }).join('')}</tr>`
    ).join('');

    document.getElementById('dbTable').classList.remove('hidden');

    // Pagination
    const pages = Math.ceil(data.total / pageSize);
    if (pages > 1) {
      let html = `<button class="page-btn" onclick="loadTable(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`;
      for (let p = Math.max(1, page - 2); p <= Math.min(pages, page + 2); p++) {
        html += `<button class="page-btn ${p === page ? 'active' : ''}" onclick="loadTable(${p})">${p}</button>`;
      }
      html += `<button class="page-btn" onclick="loadTable(${page + 1})" ${page >= pages ? 'disabled' : ''}>›</button>`;
      document.getElementById('dbPagination').innerHTML = html;
    }

  } catch (e) {
    document.getElementById('dbLoading').classList.add('hidden');
    Toast.error(e.message);
    if (e.status === 401) openApiKeyModal();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (ApiKey.get()) loadTable(1);
  else openApiKeyModal();
});
