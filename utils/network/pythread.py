import threading

class PyThread (threading.Thread):
    def __init__(self, threadID, f, param, name):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.f = f
        self.param = param
        
    def run(self):
        if self.param is None:
            self.f()
        elif hasattr(self.param, '__iter__'):
            self.f(*self.param)
        else:
            self.f(self.param)
   