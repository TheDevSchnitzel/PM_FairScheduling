import pm4py
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
import random
import itertools
from datetime import datetime, timezone
import pandas as pd
import os
import sys
from pathlib import Path
from enum import Enum

class TimestampModes(Enum):
    START   = 0
    END     = 1
    BOTH    = 2
    
class SimulationModes(Enum):
    KNOWN_FUTURE     = 0
    PREDICTED_FUTURE = 1

class Trace:
    def __init__(self, case, events):
        self.case = case     
        self.history = []      # [(start_ts, end_ts, res, (a,r,ts)) ...]
        self.future = events   # [(a,r,ts) or (a,r,ts_start, ts_end)...]
        self.currentAct = None # (start_ts, exec.res, (a,r,ts))
        self.waiting = True # Not yet started, first event has still to come
        
        
    def IsWaiting(self) -> bool:
        return self.waiting
    
    def HasRunningActivity(self) -> bool:
        return self.currentAct is not None
    
    def HasEnded(self) -> bool:
        return self.currentAct is None and len(self.future) == 0
    
    def NextEventInWindow(self, windowLower, windowUpper) -> bool:
        return len(self.future) > 0 and windowLower <= self.future[0][2] <= windowUpper
    
    def GetNextActivity(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0][0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            raise Exception("TODO: Implement!")
        else:
            raise Exception("Unknown mode for simulation!")
    
    def GetNextEvent(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            raise Exception("TODO: Implement!")
        else:
            raise Exception("Unknown mode for simulation!")
        
    def GetRemainingActivityTime(self, mode: TimestampModes,  time: int) -> int:
        if self.currentAct is None:
            return 0
        elif len(self.currentAct[2]) == 3:
            if mode == TimestampModes.END:
                if len(self.history) == 0:
                    #print("TODO: Implement? - Problematic to chose a first timestamp - Naive approach used currently")
                    return self.currentAct[2][2] - time
                else:
                    duration = (self.currentAct[2][2] - self.history[-1][3][2]) # End of current event - End of previous event (Ends are known or predicted)
                    return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
            elif mode == TimestampModes.START:
                if len(self.future) > 0:
                    duration = (self.future[0][1][2] - self.currentAct[2][2]) # Start of next event - Start of current event  (Starts are known or predicted)
                    return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
                else:
                    raise Exception("TODO: Implement!")
                    return "PROBLEM"
        elif len(self.currentAct[2]) == 4:
            duration = (self.currentAct[2][3] - self.currentAct[2][2])
            return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
        else:
            raise Exception("Illegal state!")
    
    def GetNextActivityTime(self, simMode: SimulationModes, timeMode: TimestampModes) -> int:
        if simMode == SimulationModes.KNOWN_FUTURE:
            if len(self.future) == 0:
                return 0
            
            if timeMode == TimestampModes.BOTH:
                return self.future[0][3] - self.future[0][2]
            elif timeMode == TimestampModes.START:
                if len(self.future) >= 2:
                    t = self.future[1][3][2]
                else:
                    return 0 # No information available
                return t - self.future[0][2]
            elif timeMode == TimestampModes.END:
                if self.currentAct is not None:
                    t = self.currentAct[2][2]
                elif len(self.history) > 0:
                    t = self.history[-1][3][2]
                else:
                    return 0 # No information available
                return self.future[0][2] - t
        else:
            return 0
    
    
    def EndCurrentActivity(self, time):
        if self.currentAct is None:
            raise Exception("Illegal state!")
        
        # Build (start_ts, end_ts, res, (a,r,ts) ... or (a,r,start_ts, end_ts))
        self.history.append((self.currentAct[0], time, self.currentAct[1], self.currentAct[2]))
        self.currentAct = None

        # Determine waiting status
        if len(self.future) > 0:
            self.waiting = True # Somewhere in the process
        else:
            self.waiting = False # All done here
                        
    def StartNextActivity(self, simMode, startTime, resource):
        self.waiting = False
        self.currentAct = (startTime, resource, self.GetNextEvent(simMode))
        del self.future[0]
        

def GetIntTs(datetime_ts):
    # From extractor / Bianka
    if isinstance(datetime_ts, str):
        datetime_ts = datetime.strptime(datetime_ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    return (datetime_ts - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()

def GenerateTraces(log):
    eventTraces = {str(c):[] for c in range(len(log))}
    cid = 0
    
    for trace in log:
        n = len(trace)
        
        for i in range(n):
            event = trace[i]
            
            if 'Case' in event:
                cid = str(event['Case'])
            elif 'case' in event:
                cid = str(event['case'])
            else:
                print('NO CID!')
            act = event['concept:name']
            res = event['org:resource']
            ts  = GetIntTs(event['time:timestamp'])
            
            eventTraces[cid].append((act,res,ts))
        eventTraces[cid] = Trace(str(cid), [(e[0], e[1], e[2]) for e in eventTraces[cid]])
    return [t for t in eventTraces.values()]
        

def CheckResourcesAlign(tracesA, tracesB):
    if len(tracesA) != len(tracesB):
        print(f'Error: Trace count doesn\'t match: ({len(tracesA)}/{len(tracesB)})')
        return
    
    for t in range(len(tracesA)):
        if len(tracesA[t].future) != len(tracesB[t].future):
            print(f'Error: Event count doesn\'t match: ({len(tracesA[t].future)}/{len(tracesB[t].future)}), Trace: {t}')
            #return
            continue
            
        for e in range(len(tracesA[t].future)):
            if tracesA[t].future[e][0] != tracesB[t].future[e][0]:
                print('Activities not matching')
                #return
            if tracesA[t].future[e][1] != tracesB[t].future[e][1]:
                print('Resources not matching')
                #return
    print('Traces align regarding event count, activity order and resource assignemnt!')
    
    
def main(a, b):
    logA = pm4py.read_xes(a)
    logB = pm4py.read_xes(b)

    tracesA = GenerateTraces(logA)
    tracesB = GenerateTraces(logB)
    
    #CheckResourcesAlign(tracesA, tracesB)
    for t in range(len(tracesA)):
        trace = tracesA[t]
        for e in range(len(trace.future)):
            if tracesA[t].future[e][1] == 'R2' and tracesA[t].future[e][2] <= 1590993999:
                print(f"Trace {trace.case} - {tracesA[t].future[e][0]} - {tracesA[t].future[e][1]} - { tracesA[t].future[e][2]}")
                if e > 0:
                    print(f"    {tracesA[t].future[e-1][2]}")
    
    
if __name__ == '__main__':
    main('../logs/log_ResReduced.xes', '../XX_ScheduleTesting.xes')
  