document.addEventListener('DOMContentLoaded', () => {
  // Already logged in — go straight to dashboard
  if (ApiKey.get()) window.location.href = '/';
  else document.getElementById('username').focus();
});

async function doLogin() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const errorEl  = document.getElementById('loginError');
  const btn      = document.getElementById('loginBtn');

  if (!username || !password) {
    showError('Please enter username and password.');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Signing in…';
  errorEl.style.display = 'none';

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      showError(data.error || 'Login failed.');
      return;
    }

    ApiKey.set(data.token);
    window.location.href = '/';

  } catch {
    showError('Could not reach the server. Is it running?');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Sign In';
  }
}

function showError(msg) {
  const el = document.getElementById('loginError');
  el.textContent = msg;
  el.style.display = 'block';
}
