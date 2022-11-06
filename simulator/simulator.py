from enum import Enum
import time

Callbacks = Enum('Callbacks', ['WND_START', 'WND_END', 'CALC_Fairness', 'CALC_Congestion'])

class Simulator:
    
    def __init__(self, event_dict, eventsPerWindowDict, AtoR, RtoA):
        self.P_Events = event_dict
        self.P_EventsPerWindowDict = eventsPerWindowDict
        self.P_AtoR = AtoR
        self.P_RtoA = RtoA
        
        self.R = [r for r in RtoA.keys()]
        
        self.traces = list()
        self.activeTraces = list()
        self.completedTraces = list()
        self.callbacks = { x: None for x in Callbacks }
        
        self.traceCount = 0        
        self.traces = {}
        
        self.GenerateTraceInstances()

    def register(self, callbackType, callback):
        self.callbacks[callbackType] = callback
        
    def GenerateTraceInstances(self):
        self.traces = {cid:[] for cid in set([e['cid'] for e in self.P_Events])}
        
        # Build the event traces
        for e in self.P_Events:
            self.traces[e['cid']].append(e)
        
        # Sort events in traces by timestamp
        for cid in self.traces.keys():
            self.traces[cid].sort(key=lambda e: e['ts'])
        
        self.traceCount = len(self.traces)
        
    def ApplyScheduling(self, schedule):
        pass
    
    def GetIdleResources(self):
        """Get resources currently not performing any activity and are free for scheduling"""
        return []
    
    def run(self):
        currentWindow = 0
        
        simStart = time.time()
        
        while len(self.completedTraces) != self.traceCount:
            
            # Calculate fairness ratio - { r: x \in [0, 1] for r in R }
            if self.callbacks[Callbacks.CALC_Fairness] is not None:
                fRatio = self.callbacks[Callbacks.CALC_Fairness](trace, segment, self.R)
            
            # Calculate congestion ratio - { per segment? }
            if self.callbacks[Callbacks.CALC_Congestion] is not None:
                cRatio = self.callbacks[Callbacks.CALC_Congestion](trace, segment)
            
            # Call to get the new schedule (most likely a MIP scheduling)
            if self.callbacks[Callbacks.WND_Start] is not None:
                schedule = self.callbacks[Callbacks.WND_Start](trace, segment, fRatio, cRatio)
            
            # Apply changes
            self.ApplyScheduling(schedule)
            
            events = self.P_EventsPerWindowDict[currentWindow]
            tsList = list(set([self.P_Events[id]['ts'] for id in events])).sort()
            
            currentWindow += 1
        
        print(f"Total time for simulation {time.time() - simStart :.1f}s") 
    