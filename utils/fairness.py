
def FairnessEqualWork(R):
    return {r: 1.0/len(R) for r in R}
        
def FairnessBacklogFair_TIME(activeTraces, completedTraces, R, windows, currentWindow, BACKLOG_N = 5):
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
                
        for r in R:
            resMat_TIME[r] = resMat_TIME[r] / timeTotal

        return resMat_TIME
        
def FairnessBacklogFair_WORK(activeTraces, completedTraces, R, windows, currentWindow, BACKLOG_N = 5):
        resMat_N = {r: 0 for r in R}        
        nTotal   = 0
                
        minTS = windows[max([0, currentWindow - BACKLOG_N])][0]
        maxTS = windows[currentWindow][1]
                
        for trace in completedTraces + activeTraces:
            for data in trace.history:
                if minTS <= data[0] or data[1] <= maxTS:
                    resMat_N[data[2]]   += 1
                    nTotal              += 1
        
        # Equal distribution if no traces processed so far
        if nTotal == 0:
            return {r: 1.0/len(R) for r in R}
        else:    
            for r in R:
                resMat_N[r] = resMat_N[r] / nTotal
            
            if currentWindow > 10000:
                print(resMat_N)
            return resMat_N
        