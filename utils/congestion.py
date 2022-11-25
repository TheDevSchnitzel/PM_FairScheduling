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
    print(segmentFreq)
    return segmentFreq, segmentTime, waitingTraces

def GetProgressByWaitingTimeInFrontOfActivity(A, segmentTime, waitingTraces):
    ret = {a: 1 for a in A}
    for (_, a), t in segmentTime.items():
        ret[a] += t / waitingTraces
    return ret
    
def GetProgressByWaitingNumberInFrontOfActivity(A, segmentFreq, waitingTraces):
    ret = {a: 1 for a in A}
    for (_, a), n in segmentFreq.items():
        ret[a] += n / waitingTraces
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