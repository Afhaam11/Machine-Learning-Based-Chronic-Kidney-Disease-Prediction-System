/* Runs before first paint (loaded synchronously in <head>) so there is no flash of the wrong theme. */
(function () {
  try {
    var saved = localStorage.getItem('ckdlab.theme');
    var dark = saved ? saved === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  } catch (e) { /* storage blocked: keep the light default */ }
})();
