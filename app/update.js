(() => {
  const current = document.documentElement.dataset.appVersion || '';
  async function check() {
    try {
      const r = await fetch('/api/system/version?_=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      if (!data.version || !current || data.version === current) return;
      if (window.recording === true || window.__appUpdateBusy === true) return;
      window.location.reload();
    } catch (_) {}
  }
  window.checkAppUpdate = check;
  setInterval(check, 30000);
  window.addEventListener('focus', check);
})();
