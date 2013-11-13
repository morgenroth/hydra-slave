import threading

class ConcurrentThread (threading.Thread):
    def __init__(self, func, key, data):
        threading.Thread.__init__(self)
        self.data = data
        self.key = key
        self.func = func
        self.start()
    
    def run(self):
        self.ret = self.func(self.data)
    
    def get(self):
        self.join()
        return (self.key, self.ret)

def concurrent(func, data):
    threads = []
    ret = {}
    
    for key, itm in data.iteritems():
        threads.append( ConcurrentThread(func, key, itm) )
    
    for t in threads:
        (key, data) = t.get()
        ret[key] = data
    
    return ret
