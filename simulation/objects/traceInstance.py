import pickle
from .enums import SimulationModes, TimestampModes


class Trace:
    def __init__(self, case, events, callback_PREDICT_NEXT_ACT, callback_PREDICT_ACT_DUR):
        self.case = case     
        self.history = []      # [(start_ts, end_ts, res, (a,r,ts)) ...]
        
        self.future = events # [(a,r,ts)...]
        
        # Duration of the events in 'future' (in order)
        self.durations = [1 for _ in range(len(events))]     
        
        # Lifecycle status of the events in 'future' (in order)
        self.lifecycle = []
                
        self.currentAct = None # (start_ts, exec.res, (a,r,ts))
        self.waiting    = True # Not yet started, first event has still to come

        self.PREDICT_NEXT_ACT = callback_PREDICT_NEXT_ACT
        self.PREDICT_ACT_DUR  = callback_PREDICT_ACT_DUR
        
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
            # Request the next_activity prediction, if future has a value this has already been done, do not do it again
            if len(self.future) == 0:
                self.future.append((self.PREDICT_NEXT_ACT(self), None, None)) # (a,r,ts)
            
            return self.future[0][0]
        else:
            raise Exception("Unknown mode for simulation!")
    
    def GetNextEvent(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            if len(self.future) == 0:
                self.future.append((self.PREDICT_NEXT_ACT(self), None, None)) # (a,r,ts)
            
            return self.future[0]
        else:
            raise Exception("Unknown mode for simulation!")
        
    def GetRemainingActivityTime(self, mode: TimestampModes,  time: int, simMode: SimulationModes) -> int:
        if self.currentAct is None:
            return 0
        elif len(self.durations) == 0 and simMode == SimulationModes.PREDICTED_FUTURE:
            self.durations.append(self.PREDICT_ACT_DUR(self.PREDICT_ACT_DUR(self, 'current')))    
        # elif len(self.currentAct[2]) == 3:
        #     if mode == TimestampModes.END:
        #         if len(self.history) == 0:
        #             #print("TODO: Implement? - Problematic to chose a first timestamp - Naive approach used currently")
        #             return self.currentAct[2][2] - time
        #         else:
        #             duration = (self.currentAct[2][2] - self.history[-1][3][2]) # End of current event - End of previous event (Ends are known or predicted)
        #             return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
        #     elif mode == TimestampModes.START:
        #         if len(self.future) > 0:
        #             duration = (self.future[0][1][2] - self.currentAct[2][2]) # Start of next event - Start of current event  (Starts are known or predicted)
        #             return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
        #         else:
        #             raise Exception("TODO: Implement!")
        #             return "PROBLEM"
        # elif len(self.currentAct[2]) == 4:
        #     duration = (self.currentAct[2][3] - self.currentAct[2][2])
        #     return (self.currentAct[0] + duration) - time # Start time + duration - current time = remaining time
        else:
            timePassed = time - self.currentAct[0]
            return self.durations[0] - timePassed
            # raise Exception("Illegal state!")
    
    def GetNextActivityTime(self, simMode: SimulationModes, timeMode: TimestampModes) -> int:
        if simMode == SimulationModes.KNOWN_FUTURE:
            if len(self.future) == 0:
                return 0
            else:
                if self.IsWaiting():
                    return self.durations[0]
                elif self.HasRunningActivity():
                    return self.durations[1]
                else:
                    raise Exception("Illegal state!")
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            # Request the next_activity_duration prediction, if durations has a value this has already been done, do not do it again
            if self.IsWaiting():
                if len(self.durations) == 0:
                    self.durations.append(self.PREDICT_ACT_DUR(self, 'current'))
                return self.durations[0]
            elif self.HasRunningActivity():
                if len(self.durations) == 1:
                    self.durations.append(self.PREDICT_ACT_DUR(self))
                return self.durations[1]
        else:
            return 0
    
    
    def EndCurrentActivity(self, time):
        if self.currentAct is None:
            raise Exception("Illegal state!")
        
        # Build (start_ts, end_ts, res, (a,r,ts))
        self.history.append((self.currentAct[0], time, self.currentAct[1], self.currentAct[2]))
        del self.durations[0]
        
        if len(self.lifecycle) > 0:
            del self.lifecycle[0]
            
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
        