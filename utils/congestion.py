def GetActiveSegments(activeTraces, simTime, simMode):
    segmentFreq = {}
    segmentTime = {}
    waitingTraces = 0
    
    for trace in activeTraces:
        if trace.IsWaiting():
            waitingTraces += 1
            lastAct = None
            lastTs = simTime
                
            if len(trace.history) > 0:
                lastAct = trace.history[-1][3][0]
                lastTs  = trace.history[-1][1]
            
            nextAct = trace.GetNextActivity(simMode)
            
            # Count frequency on segment
            if (lastAct, nextAct) in segmentFreq:
                segmentFreq[(lastAct, nextAct)] += 1
                
                segmentTime[(lastAct, nextAct)] += simTime - lastTs
            else:
                segmentFreq[(lastAct, nextAct)] = 1
                
                # Time spent in this segment
                segmentTime[(lastAct, nextAct)] = simTime - lastTs
    return segmentFreq, segmentTime, waitingTraces

def GetProgressByWaitingTimeInFrontOfActivity(simulatorState):
    currentWindow   = simulatorState['CurrentWindow']
    windows         = simulatorState['Windows']
    verbose         = simulatorState['Verbose']
    A               = simulatorState['A'] + [None]
    lonelyResources = simulatorState['LonelyResources']
    completedTraces = simulatorState['CompletedTraces']
    activeTraces    = simulatorState['ActiveTraces']
    simTime         = simulatorState['CurrentTimestep']
    simMode         = simulatorState['SimulationMode']
    segmentFreq, segmentTime, waitingTraces = GetActiveSegments(activeTraces, simTime, simMode)    
    
    ret = {(a,b): 0 for a in A for b in A}
    for (a, b), t in segmentFreq.items():
        ret[(a,b)] += t / waitingTraces
    return ret
    
def GetProgressByWaitingNumberInFrontOfActivity(simulatorState):
    currentWindow   = simulatorState['CurrentWindow']
    windows         = simulatorState['Windows']
    verbose         = simulatorState['Verbose']
    A               = simulatorState['A'] + [None]
    lonelyResources = simulatorState['LonelyResources']
    completedTraces = simulatorState['CompletedTraces']
    activeTraces    = simulatorState['ActiveTraces']
    simTime         = simulatorState['CurrentTimestep']
    simMode         = simulatorState['SimulationMode']
    segmentFreq, segmentTime, waitingTraces = GetActiveSegments(activeTraces, simTime, simMode)
    
    ret = {(a,b): 0 for a in A for b in A}
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