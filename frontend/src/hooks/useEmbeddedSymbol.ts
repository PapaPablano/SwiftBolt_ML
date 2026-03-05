import { useState, useEffect } from 'react';

/**
 * Listens for window.postMessage({ type: 'symbolChanged', symbol })
 * from the macOS native bridge (FrontendWebViewRepresentable.injectSymbol).
 *
 * In WKWebView, the native bridge delivers messages with e.origin === '' or
 * the page's own origin. The guard below blocks cross-origin senders in browser
 * contexts without affecting native bridge delivery.
 */
export function useEmbeddedSymbol(fallback = 'AAPL'): string {
  const [symbol, setSymbol] = useState(fallback);

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.origin !== '' && e.origin !== window.location.origin) return;
      if (e.data?.type === 'symbolChanged' && typeof e.data.symbol === 'string') {
        setSymbol(e.data.symbol);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  return symbol;
}
