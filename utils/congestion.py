def GetActiveSegments(activeTraces, simTime, simMode):
    segmentFreq = {}
    segmentTime = {}
    
    for trace in activeTraces:
        if trace.IsWaiting():
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
    return segmentFreq, segmentTime