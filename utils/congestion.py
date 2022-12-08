def GetWindowAwareSegmentData(eventA, eventB, minTS, simTime): #(Earlier Event, Later Event)
    # First event in trace, no timing data available if unfinished
    if eventA is None:
        if len(eventB) == 4: # History event
            return (None, eventB[3][0]), 0
        else: # len for current activity is 3
            # Take window aware duration
            return (None, eventB[2][0]), simTime - max(minTS, eventB[0])
    else:
        aTS_Start = eventA[0]
        aTS_End   = eventA[1]
        aAct      = eventA[3][0]

        bTS_Start = eventB[0] 
        bTS_End   = eventB[1] 
        bAct      = eventA[3][0]

        relevantTime = aTS_End
        if aTS_End < minTS:
            relevantTime = minTS
            
        backlogAwareDuration = bTS_End - relevantTime

        return (aAct,bAct), backlogAwareDuration

def GetActiveSegments(simulatorState, BACKLOG_N):
    currentWindow   = simulatorState['CurrentWindow']
    windows         = simulatorState['Windows']
    activeTraces    = simulatorState['ActiveTraces']
    completedTraces = simulatorState['CompletedTraces']
    simTime         = simulatorState['CurrentTimestep']
    simMode         = simulatorState['SimulationMode']
    timeMode        = simulatorState['TimestampMode']
    segmentFreq = {}
    segmentTime = {}
    waitingTraces = 0
    
    minTS = windows[max([0, currentWindow - BACKLOG_N])][0]

    for trace in activeTraces + completedTraces:
        if trace.IsWaiting():
            waitingTraces += 1

        # Iterate historic segments in reverse
        for i in range(1, len(trace.history) + 1):
            hEvent    = trace.history[-i] # Reversing happens here
            hTS_Start = hEvent[0] 
            hTS_End   = hEvent[1] 

            # Make sure events are in specified backlog
            if (minTS <= hTS_Start) or (minTS <= hTS_End): # No need to check upper window-border, we're in the current window anyway, history can't be more advanced than now
                if i < len(trace.history):
                    seq, time = GetWindowAwareSegmentData(trace.history[-(i+1)], hEvent, minTS, simTime)
                else: # First event in trace
                    seq, time = GetWindowAwareSegmentData(None, hEvent, minTS, simTime)

                # Update segment data                
                if seq in segmentFreq:
                    segmentFreq[seq] += 1
                    segmentTime[seq] += time
                else:
                    segmentFreq[seq] = 1
                    segmentTime[seq] = time
            else:
                # As we iterate in reverse, no earlier events will be in the backlog => Skip them
                break
        
        # Look into current segment
        if not trace.HasEnded():
            if len(trace.history) == 0:
                # (None, FirstAct) segment
                if trace.HasRunningActivity():
                    seq  = (None, trace.currentAct[2][0])
                    time = simTime - trace.currentAct[0]
                else:
                    seq  = (None, trace.GetNextActivity(simMode))
                    time = 0 # UNKNOWN
            else:
                # (Act a, Act b) segment
                lastAct = trace.history[-1][3][0]
                lastTs  = trace.history[-1][1]
                
                if trace.HasRunningActivity():
                    seq  = (lastAct, trace.currentAct[2][0])
                    time = simTime - lastTs # We are in this segment since the previous event took place
                else:
                    seq  = (lastAct, trace.GetNextActivity(simMode))
                    time = simTime - lastTs

            # Update segment data                
            if seq in segmentFreq:
                segmentFreq[seq] += 1
                segmentTime[seq] += time
            else:
                segmentFreq[seq] = 1
                segmentTime[seq] = time
    return segmentFreq, segmentTime, waitingTraces








def GetProgressByWaitingTimeInFrontOfActivity(simulatorState, BACKLOG_N = 10):
    verbose         = simulatorState['Verbose']
    A               = simulatorState['A'] + [None]
    lonelyResources = simulatorState['LonelyResources']
    completedTraces = simulatorState['CompletedTraces']
    segmentFreq, segmentTime, waitingTraces = GetActiveSegments(simulatorState, BACKLOG_N)
    
    ret = {(a,b): 1 for a in A for b in A}
    
    if waitingTraces > 0:
        for (a, b), t in segmentTime.items():
            ret[(a,b)] += t / waitingTraces
    return ret
    
def GetProgressByWaitingNumberInFrontOfActivity(simulatorState, BACKLOG_N = 10):
    verbose         = simulatorState['Verbose']
    A               = simulatorState['A'] + [None]
    lonelyResources = simulatorState['LonelyResources']
    completedTraces = simulatorState['CompletedTraces']
    segmentFreq, segmentTime, waitingTraces = GetActiveSegments(simulatorState, BACKLOG_N)
    
    ret = {(a,b): 1 for a in A for b in A}

    if waitingTraces > 0:
        for (a, b), n in segmentFreq.items():
            ret[(a,b)] += n / waitingTraces
    return ret
    
def GetCategorizedTraces(activeTraces, currentWindowLower, currentWindowUpper, simTime):
    arrive = []
    leave  = []
    cross  = []
    
    for trace in activeTraces:
        if trace.IsWaiting():
            pass
        else:
            trace.currentAct[0]