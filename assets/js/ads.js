/**
 * Ad Network Loader
 * Dynamic script injection to bypass static content filters.
 */
(function () {
  var _0 = [
    'aHR0cHM6Ly9wbDMxMTA5MDYwLnByb2ZpdGFibGVyYXRlY3BtbmV0d29yay5jb20vMTUvNzcvZTQvMTU3N2U0NDVkNTA1MmQzMmI4MTcxYzA1NWM0YWFlMDMuanM=',
    'aHR0cHM6Ly9wbDMxMTA5MDYxLnByb2ZpdGFibGVyYXRlY3BtbmV0d29yay5jb20vOTZkZWY2ZjBjYzRkYmE3MmFkNzgxYzkzZTIxZjYxZmQvaW52b2tlLmpz'
  ];

  function _d(s) {
    try { return atob(s); } catch (e) { return ''; }
  }

  function _injectScript(src, opts) {
    var el = document.createElement('script');
    el.src = src;
    if (opts) {
      if (opts.async)           el.async = true;
      if (opts.cfasync === false) el.setAttribute('data-cfasync', 'false');
    }
    (document.head || document.documentElement).appendChild(el);
  }

  // Popunder
  _injectScript(_d(_0[0]));

  // Social Bar
  _injectScript(_d(_0[1]), { async: true, cfasync: false });
})();
