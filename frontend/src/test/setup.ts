import '@testing-library/jest-dom/vitest'

// Node 25's built-in global `localStorage` shadows jsdom's and is a
// non-functional stub unless the process is started with
// `--localstorage-file` — neither `localStorage.x` nor `window.
// localStorage.x` work under it (confirmed: prototype is bare `Object.
// prototype`, no Storage methods at all). Sidebar.tsx (feat/sidebar-
// restructure) is this project's first `localStorage` consumer, so this
// had gone unnoticed until now. Replace it with a minimal in-memory
// Storage implementation for both the global and `window` bindings.
class MemoryStorage implements Storage {
  private store = new Map<string, string>()
  get length() {
    return this.store.size
  }
  clear() {
    this.store.clear()
  }
  getItem(key: string) {
    return this.store.has(key) ? this.store.get(key)! : null
  }
  key(index: number) {
    return Array.from(this.store.keys())[index] ?? null
  }
  removeItem(key: string) {
    this.store.delete(key)
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value))
  }
}

const memoryStorage = new MemoryStorage()
Object.defineProperty(globalThis, 'localStorage', {
  value: memoryStorage,
  configurable: true,
  writable: true,
})
Object.defineProperty(window, 'localStorage', {
  value: memoryStorage,
  configurable: true,
  writable: true,
})
