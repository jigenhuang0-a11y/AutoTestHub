/**
 * localStorage 封装，带 JSON 序列化和命名空间前缀
 * 所有数据以 ah_ 为前缀，便于清理和隔离
 */
export const storage = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(`ah_${key}`)
      return raw !== null ? JSON.parse(raw) : fallback
    } catch {
      return fallback
    }
  },

  set(key, value) {
    try {
      localStorage.setItem(`ah_${key}`, JSON.stringify(value))
    } catch (e) {
      console.warn(`[storage] 写入失败: ${key}`, e)
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(`ah_${key}`)
    } catch {}
  },

  /** 获取所有 ah_ 前缀的键 */
  keys() {
    const result = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith('ah_')) result.push(k.slice(3))
    }
    return result
  },
}
