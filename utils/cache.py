from datetime import datetime, timedelta
import threading

class Cache:
    """
    Basit ve hızlı bir RAM cache sistemi.
    Thread-safe çalışır ve belirlenen sürede otomatik temizlenir.
    """

    def __init__(self, duration_minutes=10):
        self.duration = timedelta(minutes=duration_minutes)
        self.data = {}             # {"general": [...], "sports": [...]}
        self.timestamps = {}       # {"general": datetime, ...}
        self.lock = threading.Lock()

    def get(self, key):
        """Cache geçerliyse döner, değilse None döner."""
        with self.lock:
            if key in self.data and key in self.timestamps:
                if datetime.now() - self.timestamps[key] < self.duration:
                    return self.data[key]
        
        return None

    def set(self, key, value):
        """Cache'e yeni veri yazar."""
        with self.lock:
            self.data[key] = value
            self.timestamps[key] = datetime.now()

    def clear(self):
        """Tüm cache'i temizler."""
        with self.lock:
            self.data = {}
            self.timestamps = {}

    def clear_key(self, key):
        """Belirli bir kategorinin cache'ini temizler."""
        with self.lock:
            if key in self.data:
                del self.data[key]
            if key in self.timestamps:
                del self.timestamps[key]
