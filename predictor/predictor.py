from utils.network.server import Server
from utils.network.enums import Callbacks
from utils.network.pythread import PyThread
from predictor.dataPrep import CreateOneHotEncoding
from predictor.model import PredictionModel
import queue
import json

class PredictorService:
    def __init__(self, host, port, modelPath, bufferSize=1024, allowOpenConnections=True, verbose=False):
        # queue.Queue() is a thread-safe module
        self.NextActivityQueue     = queue.Queue()
        self.ActivityDurationQueue = queue.Queue()
        
        self.Server = Server(host, port, bufferSize, allowOpenConnections)
        self.Server.Register(Callbacks.MESSAGE_RECEIVED, self.__HandleNewRequest)

        self.QueueWorker = PyThread(-1, self.__WorkQueue, None, "Queue-Worker")
        
        self.Model = PredictionModel()
        self.Model.Load(modelPath)

        self.MapOH_A = {}
        self.MapOH_R = {}
        self.Aborted = False
        
    def __HandleNewRequest(self, data):
        (clientNr, address, bytestring) = data

        try:
            msg = json.loads(bytestring.decode())
        except:
            print(f"UNREADABLE MESSAGE RECEIVED IN PREDICTOR: '{bytestring}' from {address}")
            return

        if msg.get('Task') == 'next_activity':
            self.NextActivityQueue.put((msg['ACT'], msg['RES'], msg['CTX']))
        elif msg.get('Task') == 'next_timestamp':
            self.ActivityDurationQueue.put((msg['ACT'], msg['RES'], msg['CTX']))
    
    def __WorkQueue(self):
        while not self.Aborted:
            while not self.NextActivityQueue.empty():
                item = self.NextActivityQueue.get(block=False)
                
                self.NextActivityQueue.task_done()
                
            while not self.ActivityDurationQueue.empty():
                item = self.ActivityDurationQueue.get(block=False)
                
                self.ActivityDurationQueue.task_done()


    def StartService(self, A, R):
        self.MapOH_A, self.MapOH_R = CreateOneHotEncoding(sorted(A), sorted(R))

        self.QueueWorker.start()
        self.Server.RunServer()
        
    def StopService(self):
        self.Aborted = True
        self.Server.Stop()