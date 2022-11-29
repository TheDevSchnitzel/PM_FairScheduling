

def EventDurationsByMinPossibleTime(R, traces):
    # Calculate activity durations properly (traces list is passed by reference, just modify it)
    resList = {r:[] for r in R}
    traceDict = {trace.case: trace for trace in traces}
    for trace in traces:
        cid = trace.case
        
        for event in trace.future:
            act = event[0]
            res = event[1]
            ts  = event[2]
            
            resList[res].append((act, ts, cid))
    
    resList = {r: sorted(resList[r], key=lambda x: x[1]) for r in R} # Order by TS
    for r in R:
        for i in range(len(resList[r])):
            (act, ts, cid) = resList[r][i]
            trace = traceDict[cid]
            
            if i > 0:
                resBasedDuration = ts - resList[r][i-1][1] # Time between previous and current event on resource r
            else:
                resBasedDuration = 1
            
            for j in range(len(trace.future)):
                fAct = trace.future[j][0]
                fRes = trace.future[j][1]
                fTs  = trace.future[j][2]
                
                if j > 0:
                    traceBasedDuration = fTs - trace.future[j-1][2] # Time between previous and current event in the trace
                else:
                    traceBasedDuration = 1
                
                # Find the matching event
                if fAct == act and fRes == r and fTs == ts:
                    trace.durations[j] = int(min(resBasedDuration, traceBasedDuration))


def EventDurationsByInterEventTimeInTrace(R, traces):
    """Naive approach - Leads to far too long activity times causing the process to be delayed significantly"""
    for trace in traces:
        for i in range(len(trace.future)):
            if i == 0:
                trace.durations[i] = 1
            else:
                trace.durations[i] = trace.future[i][2] - trace.future[i - 1][2] # Time between events