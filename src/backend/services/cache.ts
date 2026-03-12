export class CacheService {
  private kv: KVNamespace;
  
  constructor(kv: KVNamespace) {
    this.kv = kv;
  }
  
  async get<T>(key: string): Promise<T | null> {
    try {
      const value = await this.kv.get(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      console.error('Cache get error:', error);
      return null;
    }
  }
  
  async set(key: string, value: any, ttlSeconds?: number): Promise<boolean> {
    try {
      const options = ttlSeconds ? { expirationTtl: ttlSeconds } : undefined;
      await this.kv.put(key, JSON.stringify(value), options);
      return true;
    } catch (error) {
      console.error('Cache set error:', error);
      return false;
    }
  }
  
  async delete(key: string): Promise<boolean> {
    try {
      await this.kv.delete(key);
      return true;
    } catch (error) {
      console.error('Cache delete error:', error);
      return false;
    }
  }
  
  async clear(prefix: string): Promise<boolean> {
    try {
      const list = await this.kv.list({ prefix });
      const deletePromises = list.keys.map(key => this.kv.delete(key.name));
      await Promise.all(deletePromises);
      return true;
    } catch (error) {
      console.error('Cache clear error:', error);
      return false;
    }
  }
  
  async exists(key: string): Promise<boolean> {
    try {
      const value = await this.kv.get(key, { stream: true });
      return value !== null;
    } catch (error) {
      console.error('Cache exists error:', error);
      return false;
    }
  }
  
  async getMultiple<T>(keys: string[]): Promise<(T | null)[]> {
    const promises = keys.map(key => this.get<T>(key));
    return Promise.all(promises);
  }
  
  async setMultiple(entries: Array<{ key: string; value: any; ttlSeconds?: number }>): Promise<boolean[]> {
    const promises = entries.map(entry => this.set(entry.key, entry.value, entry.ttlSeconds));
    return Promise.all(promises);
  }

  async getBuffer(key: string): Promise<ArrayBuffer | null> {
    try {
      return await this.kv.get(key, { type: 'arrayBuffer' });
    } catch (error) {
      console.error('Cache getBuffer error:', error);
      return null;
    }
  }

  async setBuffer(key: string, value: ArrayBuffer, ttlSeconds?: number): Promise<boolean> {
    try {
      const options = ttlSeconds ? { expirationTtl: ttlSeconds } : undefined;
      await this.kv.put(key, value, options);
      return true;
    } catch (error) {
      console.error('Cache setBuffer error:', error);
      return false;
    }
  }
}
