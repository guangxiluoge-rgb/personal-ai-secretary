(() => {
  const current = document.documentElement.dataset.appVersion || '';
  let busy = false;
  window.setAppUpdateBusy = (value) => { busy = Boolean(value); };
  async function check() {
    try {
      const r = await fetch('/api/system/version?_=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      if (!data.version || !current || data.version === current) return;
      if (busy) {
        window.__pendingAppUpdate = data.version;
        return;
      }
      window.location.reload();
    } catch (_) {}
  }
  window.checkAppUpdate = check;
  setInterval(check, 30000);
  window.addEventListener('focus', check);
})();
