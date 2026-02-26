// In-memory LRU cache implementation
// Suitable for hot, short-lived data with automatic eviction

import type { Cache, CacheEntry } from "./interface.ts";

export class MemoryCache implements Cache {
  private cache: Map<string, CacheEntry<unknown>>;
  private tagIndex: Map<string, Set<string>>; // tag -> set of keys
  private maxSize: number;
  private hits: number = 0;
  private misses: number = 0;

  constructor(maxSize: number = 1000) {
    this.cache = new Map();
    this.tagIndex = new Map();
    this.maxSize = maxSize;
  }

  async get<T>(key: string): Promise<T | null> {
    const entry = this.cache.get(key) as CacheEntry<T> | undefined;

    if (!entry) {
      this.misses++;
      return null;
    }

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      this.misses++;
      return null;
    }

    // Move to end (most recently used) for LRU
    this.cache.delete(key);
    this.cache.set(key, entry);
    this.hits++;

    return entry.value;
  }

  async set<T>(
    key: string,
    value: T,
    ttlSeconds: number,
    tags?: string[],
  ): Promise<void> {
    // Evict oldest entry if at capacity
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) {
        await this.delete(firstKey);
      }
    }

    const expiresAt = Date.now() + ttlSeconds * 1000;
    const entry: CacheEntry<T> = { value, expiresAt, tags };

    this.cache.set(key, entry as CacheEntry<unknown>);

    // Update tag index
    if (tags) {
      for (const tag of tags) {
        if (!this.tagIndex.has(tag)) {
          this.tagIndex.set(tag, new Set());
        }
        this.tagIndex.get(tag)!.add(key);
      }
    }
  }

  async delete(key: string): Promise<void> {
    const entry = this.cache.get(key);
    if (!entry) return;

    // Remove from tag index
    if (entry.tags) {
      for (const tag of entry.tags) {
        const keys = this.tagIndex.get(tag);
        if (keys) {
          keys.delete(key);
          if (keys.size === 0) {
            this.tagIndex.delete(tag);
          }
        }
      }
    }

    this.cache.delete(key);
  }

  async invalidateByTag(tag: string): Promise<void> {
    const keys = this.tagIndex.get(tag);
    if (!keys) return;

    for (const key of keys) {
      await this.delete(key);
    }
  }

  async clear(): Promise<void> {
    this.cache.clear();
    this.tagIndex.clear();
    this.hits = 0;
    this.misses = 0;
  }

  async getStats(): Promise<{ hits: number; misses: number; size: number }> {
    // Clean up expired entries before reporting size
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiresAt) {
        await this.delete(key);
      }
    }

    return {
      hits: this.hits,
      misses: this.misses,
      size: this.cache.size,
    };
  }
}
