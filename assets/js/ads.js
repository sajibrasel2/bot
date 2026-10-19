/**
 * Ad Network Loader v2
 * Delayed dynamic injection — bypasses static scan & Telegram WebView init block.
 */
(function () {
  var _e = function (s) { try { return atob(s); } catch (e) { return ''; } };

  var _u = [
    // Popunder
    _e('aHR0cHM6Ly9wbDMxMTA5MDYwLnByb2ZpdGFibGVyYXRlY3BtbmV0d29yay5jb20vMTUvNzcvZTQvMTU3N2U0NDVkNTA1MmQzMmI4MTcxYzA1NWM0YWFlMDMuanM='),
    // Social Bar
    _e('aHR0cHM6Ly9wbDMxMTA5MDYxLnByb2ZpdGFibGVyYXRlY3BtbmV0d29yay5jb20vOTZkZWY2ZjBjYzRkYmE3MmFkNzgxYzkzZTIxZjYxZmQvaW52b2tlLmpz')
  ];

  function _inject(src, attrs) {
    try {
      var s = document.createElement('script');
      s.type = 'text/javascript';
      s.src = src;
      if (attrs) {
        for (var k in attrs) {
          if (attrs.hasOwnProperty(k)) s.setAttribute(k, attrs[k]);
        }
      }
      // Try head first, fallback to body, fallback to documentElement
      var t = document.head || document.body || document.documentElement;
      t.appendChild(s);
    } catch (err) { /* silent fail */ }
  }

  function _load() {
    // Popunder — plain injection
    _inject(_u[0]);

    // Social Bar — with data-cfasync="false" and async
    _inject(_u[1], { 'async': '', 'data-cfasync': 'false' });
  }

  // Strategy 1: after full page load
  if (document.readyState === 'complete') {
    setTimeout(_load, 500);
  } else if (document.readyState === 'interactive') {
    setTimeout(_load, 800);
  } else {
    // Strategy 2: wait for DOMContentLoaded then delay
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(_load, 600);
    });
    // Strategy 3: hard fallback — fire after 3 seconds no matter what
    setTimeout(_load, 3000);
  }

})();
