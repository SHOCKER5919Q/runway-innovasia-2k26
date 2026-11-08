import "@testing-library/dom";

// Node 26 exposes its own `localStorage` global that is unavailable unless
// the runtime is started with --localstorage-file. It shadows the jsdom
// implementation, so every read throws. Bind the jsdom one explicitly.
if (typeof window !== "undefined") {
  const store = new Map<string, string>();
  const shim: Storage = {
    get length() { return store.size; },
    key: (i: number) => [...store.keys()][i] ?? null,
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: shim, writable: true, configurable: true,
  });
  Object.defineProperty(window, "localStorage", {
    value: shim, writable: true, configurable: true,
  });
}

// jsdom implements neither of these, and both are used by the chart and
// motion layers. Stubbing them here keeps every component test from having
// to know that.
if (!globalThis.matchMedia) {
  globalThis.matchMedia = ((q: string) => ({
    matches: false, media: q, onchange: null,
    addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false,
  })) as unknown as typeof globalThis.matchMedia;
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {} unobserve() {} disconnect() {}
  } as unknown as typeof globalThis.ResizeObserver;
}
