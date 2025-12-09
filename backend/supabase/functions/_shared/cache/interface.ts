// Cache interface: provider-agnostic caching layer
// Supports TTL-based expiration and tag-based invalidation

export interface CacheEntry<T> {
  value: T;
  expiresAt: number; // Unix timestamp in milliseconds
  tags?: string[];
}

export interface Cache {
  /**
   * Get a value from the cache
   * Returns null if key doesn't exist or has expired
   */
  get<T>(key: string): Promise<T | null>;

  /**
   * Set a value in the cache with TTL (in seconds)
   */
  set<T>(key: string, value: T, ttlSeconds: number, tags?: string[]): Promise<void>;

  /**
   * Delete a specific key from the cache
   */
  delete(key: string): Promise<void>;

  /**
   * Invalidate all entries with a specific tag
   */
  invalidateByTag(tag: string): Promise<void>;

  /**
   * Clear all entries from the cache
   */
  clear(): Promise<void>;

  /**
   * Get cache statistics (optional, for observability)
   */
  getStats?(): Promise<{ hits: number; misses: number; size: number }>;
}
