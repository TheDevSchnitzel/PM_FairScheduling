import pickle
from .enums import SimulationModes, TimestampModes


class Trace:
    def __init__(self, case, events, callback_PREDICT_NEXT_ACT, callback_PREDICT_ACT_DUR):
        self.case = case     
        self.history = []      # [(start_ts, end_ts, res, (a,r,ts)) ...]
        
        self.future  = events # [(a,r,ts)...]
        
        # Duration of the events in 'future' (in order)
        self.durations = [1 for _ in range(len(events))]     
        
        # Lifecycle status of the events in 'future' (in order)
        self.lifecycle = []
                
        self.currentAct = None # (start_ts, exec.res, (a,r,ts))
        self.waiting    = True # Not yet started, first event has still to come

        self.PREDICT_NEXT_ACT = callback_PREDICT_NEXT_ACT
        self.PREDICT_ACT_DUR  = callback_PREDICT_ACT_DUR

        # Set the initial event as known as it is the first time the case occurs and no information could be used for predictions otherwise
        self.PRED_NextActivity            = self.future[0][0]
        self.PRED_NextActivityDuration    = 1
        self.PRED_CurrentActivityDuration = None
    
    def PRED_UpdateNextActivityIfWrong(self):
        """Returns false if the next activity was correctly predicted, True otherwise"""
        act = self.GetNextActivity(SimulationModes.PREDICTED_FUTURE)
        if act != self.future[0][0]:
            self.PRED_NextActivity = self.future[0][0]
            #print(f'Wrong prediction {act} instead of {self.PRED_NextActivity}!')
            return True
        return False

    def IsWaiting(self) -> bool:
        return self.waiting
    
    def HasRunningActivity(self) -> bool:
        return self.currentAct is not None
    
    def HasEnded(self) -> bool:
        return self.currentAct is None and len(self.future) == 0
    
    def NextEventInWindow(self, windowLower, windowUpper) -> bool:
        #WARNING - PREDICTION MODE: We use the actual data of the event log to determine the starting point
        return len(self.future) > 0 and windowLower <= self.future[0][2] <= windowUpper
    
    def GetNextActivity(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0][0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            # Request the next_activity prediction, if future has a value this has already been done, do not do it again
            if self.PRED_NextActivity is None:
                self.PRED_NextActivity = self.PREDICT_NEXT_ACT(self)
                
            return self.PRED_NextActivity
        else:
            raise Exception("Unknown mode for simulation!")
    
    def GetNextEvent(self, simMode: SimulationModes) -> str:
        if simMode == SimulationModes.KNOWN_FUTURE:
            return self.future[0]
        elif simMode == SimulationModes.PREDICTED_FUTURE:
            if self.PRED_NextActivity is None:
                self.PRED_NextActivity = self.PREDICT_NEXT_ACT(self)
            return (self.PRED_NextActivity, None, None) # (a,r,ts)
            
        else:
            raise Exception("Unknown mode for simulation!")
        
    def GetRemainingActivityTime(self, mode: TimestampModes,  time: int, simMode: SimulationModes, real=False) -> int:
        """real specifies whether to return the predicted value (used to generate schedules) or the value from history data (used to actually end an activity and release a resource)"""
        if self.currentAct is None:
            return 0
        elif simMode == SimulationModes.PREDICTED_FUTURE and not real:
            if self.PRED_CurrentActivityDuration is None:
                self.PRED_CurrentActivityDuration = self.PREDICT_ACT_DUR(self, True)
            timePassed = time - self.currentAct[0]
            return self.PRED_CurrentActivityDuration - timePassed

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
            if self.PRED_NextActivityDuration is not None:
                return self.PRED_NextActivityDuration
            elif self.IsWaiting():
                self.PRED_NextActivityDuration = self.PREDICT_ACT_DUR(self, True)
                return self.PRED_NextActivityDuration
            elif self.HasRunningActivity():
                self.PRED_NextActivityDuration = self.PREDICT_ACT_DUR(self)
                return self.PRED_NextActivityDuration
        else:
            return 0
    
    
    def EndCurrentActivity(self, time, simMode : SimulationModes):
        if self.currentAct is None:
            raise Exception("Illegal state!")
        
        # Build (start_ts, end_ts, res, (a,r,ts))
        self.history.append((self.currentAct[0], time, self.currentAct[1], self.currentAct[2]))
        
        if len(self.durations) > 0:
            del self.durations[0]
        
        if len(self.lifecycle) > 0:
            del self.lifecycle[0]
            
        self.currentAct = None

        # Determine waiting status
        if len(self.future) > 0 or simMode == SimulationModes.EVENT_STREAM:
            self.waiting = True # Somewhere in the process or not officialy ended by eventstream
        else:
            self.waiting = False # All done here
                        
    def StartNextActivity(self, simMode, startTime, resource):
        self.waiting = False
        self.currentAct = (startTime, resource, self.GetNextEvent(simMode))

        # Update prediction information
        self.PRED_CurrentActivityDuration = self.PRED_NextActivityDuration
        self.PRED_NextActivityDuration    = None
        self.PRED_NextActivity            = None

        if len(self.future) > 0:
            del self.future[0]
        