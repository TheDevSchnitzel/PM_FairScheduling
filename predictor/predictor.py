from utils.network.server import Server
from utils.network.enums import Callbacks
from utils.network.pythread import PyThread
from predictor.dataPrep import CreateOneHotEncoding
from predictor.model import PredictionModel
import queue
import pickle
import threading
import sys
import traceback

class PredictorService:
    def __init__(self, host, port, modelPathNextAct, modelPathActDur, bufferSize=1024, allowOpenConnections=True, verbose=False):
        # queue.Queue() is a thread-safe module
        self.Queue = queue.Queue()

        
        self.Server = Server(host, port, bufferSize, allowOpenConnections, verbose)
        self.Server.Register(Callbacks.MESSAGE_RECEIVED, self.__HandleNewRequest)

        self.QueueWorker = PyThread(-1, self.__WorkQueue, None, "Queue-Worker")
        
        self.ModelNextAct = PredictionModel()
        self.ModelNextAct.Load(modelPathNextAct)
        
        self.ModelActDur = PredictionModel()
        self.ModelActDur.Load(modelPathActDur)
                
        self.Aborted = False
        self.Verbose = verbose
        
    def __HandleNewRequest(self, clientNr, address, bytestring):
        try:
            msg = pickle.loads(bytestring)
        except:
            print(f"UNREADABLE MESSAGE RECEIVED IN PREDICTOR: '{bytestring}' from {address}")
            return
            
        if self.Verbose:                    
            print(f'Predictor service received new task from {clientNr} - {address}!')

        # Used format: pickle.dumps({'Task': task, 'Trace': trace, 'ID': id})
        if msg.get('Task') == 'next_activity':
            self.Queue.put((*self.__ExtractDescriptorAndContext(msg['Trace']), msg['ID'], clientNr, msg.get('Task')))
        elif msg.get('Task') == 'duration':
            self.Queue.put((*self.__ExtractDescriptorAndContext(msg['Trace'], useNextAct=(not msg['CurrentActivity'])), msg['ID'], clientNr, msg.get('Task')))
    
    def __WorkQueue(self):
        while not self.Aborted:
            try:
                (act,res), ctx, id, clientNr, task = self.Queue.get(timeout=5)
                
                if self.Verbose:                    
                    print(f'Predictor service working on {task} for {id}...')
                
                try:
                    if task == 'next_activity':
                        result, _ = self.ModelNextAct.Predict((act,res), ctx)
                    elif task == 'duration':
                        result, _ = self.ModelActDur.Predict((act,res), ctx)
                except:
                    traceback.print_exc()

                if self.Verbose:
                    print(f'    -> ({act},{res}) with ({ctx}) TO {result}')
                    print(f"    ...done: '{result}' - Sending result...", sep='')

                self.Server.SendMessage(clientNr, pickle.dumps({'ID':id, 'Result': result}))
                
                if self.Verbose:                    
                    print('...done')

                self.Queue.task_done()
            except:
                pass
                

    def __ExtractDescriptorAndContext(self, trace, useNextAct=False):
        # None will be used as a token for a case awaiting its first event
        currentAct = None
        
        # None will be used as token to show unknown assignment
        currentRes = None
        ctx = []
                
        if trace.currentAct is None:
            if len(trace.history) > 0:
                currentAct = trace.history[-1][3][0]
                currentRes = trace.history[-1][2]                
                ctx = [(x[3][0], x[2]) for x in trace.history[:-1]]
        else:
            currentAct = trace.currentAct[2][0]
            currentRes = trace.currentAct[1]
            ctx = [(x[3][0], x[2]) for x in trace.history]
        
        if useNextAct and len(trace.future) > 0:
            ctx.append((currentAct, currentRes))
            currentAct = trace.future[0][0]
            currentRes = None
            
        return (currentAct, currentRes), ctx

    def StartService(self, standalone=False):
        if self.Verbose:
            print('Starting predictor service!')

        self.QueueWorker.start()
        self.Server.RunServer(standalone)
        
        if self.Verbose:
            print('Predictor service up and running!')
        
    def StopService(self):
        if self.Verbose:
            print('Stopping predictor service!')

        self.Aborted = True
        self.Server.Stop()