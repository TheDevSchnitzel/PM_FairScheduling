
def FairnessEqualWork(R):
    return {r: 1.0/len(R) for r in R}
        
def FairnessBacklogFair_TIME(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow, BACKLOG_N = 5):
        resMat_TIME = {r:0 for r in R}
        
        timeTotal = 0
                
        minTS = windows[max([0, currentWindow - BACKLOG_N])][0]
        maxTS = windows[currentWindow][1]
                
        for trace in completedTraces + activeTraces:
            for data in trace.history:
                if minTS <= data[0] or data[1] <= maxTS:                    
                    start = data[0]
                    if data[0] < minTS:
                        start = minTS
                    end = data[1]
                    if maxTS < data[1]:
                        end = maxTS
                    
                    resMat_TIME[data[2]] += end-start
                    timeTotal += end-start
        
        if timeTotal > 0:   
            for r in R:
                resMat_TIME[r] = 1 - resMat_TIME[r] / timeTotal # n/tot: How much work has the resource done, 1-: how much is still to do
                    
                # Avoid stalling
                if resMat_TIME[r] == 0:
                    resMat_TIME[r] = 0.001
            return resMat_TIME
        else:
            return {r: 1.0/len(R) for r in R}
        
def FairnessBacklogFair_WORK(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow, BACKLOG_N = 5):
        resMat_N = {r: 0 for r in R if r not in LonelyResources}        
        nTotal   = 0
                
        minTS = windows[max([0, currentWindow - BACKLOG_N])][0]
        maxTS = windows[currentWindow][1]
                
        for trace in completedTraces + activeTraces:
            #print(trace.history)
            for data in trace.history:
                if minTS <= data[0] or data[1] <= maxTS:
                    # Exclude resources that are the only ones able to perform a specific activity from this calculation
                    if data[2] not in LonelyResources:
                        resMat_N[data[2]]   += 1
                        nTotal              += 1
        
        # Equal distribution if no traces processed so far
        if nTotal == 0:
            return {r: 1.0/len(R) for r in R}
        else:    
            for r in resMat_N:
                resMat_N[r] = 1 - (resMat_N[r] / nTotal) # n/tot: How much work has the resource done, 1-: how much is still to do
                
                # Avoid stalling
                if resMat_N[r] == 0:
                    resMat_N[r] = 0.001
            
            return resMat_N
        