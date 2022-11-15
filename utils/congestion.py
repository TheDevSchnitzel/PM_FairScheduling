def GetActiveSegments(activeTraces, simTime):
    segmentFreq = {}
    segmentTime = {}
    
    for trace in activeTraces:
        lastAct = None
            
        if len(trace.history) > 0:
            lastAct = trace.history[-1][3][0]
        
        nextAct = trace.currentAct[2][0]
        
        # Count frequency on segment
        if (lastAct, nextAct) in segmentFreq:
            segmentFreq[(lastAct, nextAct)] += 1
            
            segmentTime[(lastAct, nextAct)] += simTime - trace.currentAct[0]
        else:
            segmentFreq[(lastAct, nextAct)] = 1
            
            # Time spent in this segment
            segmentTime[(lastAct, nextAct)] = simTime - trace.currentAct[0]
    return segmentFreq, segmentTime