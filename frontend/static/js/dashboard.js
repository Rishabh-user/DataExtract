async function loadStats() {
  try {
    const stats = await apiFetch('/api/stats');
    document.getElementById('stat-total').textContent     = stats.total_documents;
    document.getElementById('stat-completed').textContent = stats.completed;
    document.getElementById('stat-pages').textContent     = stats.total_pages_extracted;
    document.getElementById('stat-keys').textContent      = stats.active_keys;

    // Show current project name
    const projEl = document.getElementById('stat-project');
    if (projEl && stats.project_name) {
      projEl.textContent = stats.project_name;
      projEl.closest('.card')?.classList.remove('hidden');
    }

    // File type breakdown
    const bd = stats.file_type_breakdown || {};
    const typeEl = document.getElementById('typeBreakdown');
    const entries = Object.entries(bd).sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
      typeEl.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div><p>No documents yet.</p></div>';
    } else {
      const total = entries.reduce((s, [, v]) => s + v, 0);
      typeEl.innerHTML = entries.map(([type, count]) => {
        const pct = Math.round((count / total) * 100);
        return `<div style="margin-bottom:12px">
          <div class="flex-between text-sm mb-1">
            <span class="font-mono">${escapeHtml(type)}</span>
            <span class="text-muted">${count} file${count !== 1 ? 's' : ''} (${pct}%)</span>
          </div>
          <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
        </div>`;
      }).join('');
    }
  } catch (e) {
    document.getElementById('typeBreakdown').innerHTML =
      `<div class="alert alert-error text-sm">${escapeHtml(e.message)}</div>`;
    if (e.status === 401) Toast.warn('Set your API key to load stats.');
  }
}

async function loadRecent() {
  try {
    const data = await apiFetch('/api/filter?page=1&size=5');
    const el = document.getElementById('recentDocs');
    if (!data.results.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">📂</div><p>No documents yet. <a href="/upload">Upload one.</a></p></div>';
      return;
    }
    el.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>#</th><th>File</th><th>Type</th><th>Status</th><th></th></tr></thead>
      <tbody>${data.results.map(d => `<tr>
        <td class="text-muted text-sm">${d.id}</td>
        <td><span class="truncate" style="display:inline-block;max-width:200px" title="${escapeHtml(d.file_name)}">${escapeHtml(d.file_name)}</span></td>
        <td><span class="badge badge-info font-mono">${escapeHtml(d.file_type)}</span></td>
        <td>${badge(d.status)}</td>
        <td><a href="/view/${d.id}" class="btn btn-ghost btn-sm">View</a></td>
      </tr>`).join('')}</tbody>
    </table></div>`;
  } catch (e) {
    document.getElementById('recentDocs').innerHTML =
      `<div class="alert alert-error text-sm">${escapeHtml(e.message)}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (ApiKey.get()) {
    loadStats();
    loadRecent();
  } else {
    ['typeBreakdown','recentDocs'].forEach(id => {
      document.getElementById(id).innerHTML =
        '<div class="empty-state"><p class="text-muted text-sm">Set an API key to load data.</p></div>';
    });
    ['stat-total','stat-completed','stat-pages','stat-keys'].forEach(id => {
      document.getElementById(id).textContent = '—';
    });
  }
});
