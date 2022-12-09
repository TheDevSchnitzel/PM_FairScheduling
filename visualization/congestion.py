import pm4py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
from utils.extractor import ts_to_int as GetIntTs
from utils.EL_Helper import GetSegments, GetActivities, GetWindows


from time import time

def GetWindowIndex(windows, time):
    low  = windows[0][0]
    high = windows[len(windows.keys()) - 1][1]
    wDur = (high - low) / (len(windows.keys()) - 1)
    dur  = (high - low) / 2
        
    while dur > 1:
        if low + dur < time:
            low += dur
            dur /= 2
        elif low + dur > time:
            high -= dur
            dur /= 2
        else:
            break
    
    # Find the matching window (the bin search isn't 100% accurate, eyeballed)
    idx = int((low - windows[0][0]) / wDur)
    for i in range(idx, len(windows.keys())):
        if windows[i][0] <= time <= windows[i][1]:
            return i
    
    # Invalid window
    if windows[len(windows.keys()) - 1][1] < time:
        return -1
    
    print(len(windows.keys()))
    print(time)
    print(windows[idx-1])
    print(windows[idx])
    print(windows[idx+1])
    print('############################')
    for i in range(idx, len(windows.keys())):
        print(f'{i} - {windows[i]}')
        if windows[i][0] <= time <= windows[i][1]:
            return i
    raise('ERROR!')

def GetActiveSegments(log):
    windows  = GetWindows(log, lambda no_events: 1 * math.ceil(math.sqrt(no_events)))
    segments = GetSegments(log)
    segmentTime = {w:{(a,b): 0 for (a,b) in segments} for w in windows}
            
    for trace in log:
        n = len(trace)
        
        lastAct = 'None'
        lastTs = GetIntTs(trace[0]['time:timestamp'])
        
        for i in range(n):
            event = trace[i]
            nextAct = event['concept:name']
            ts  = GetIntTs(event['time:timestamp'])
            w = GetWindowIndex(windows, ts)
            
            if w != -1:
                low  = windows[w][0]
                high = windows[w][1]
                
                if lastTs < low and low <= ts <= high:   # Current is in
                    segmentTime[w][(lastAct, nextAct)] += ts - low
                elif low <= lastTs <= high and low <= ts <= high: # Both are in
                    segmentTime[w][(lastAct, nextAct)] += ts - lastTs
                elif low <= lastTs <= high and high < ts: # Old is in
                    segmentTime[w][(lastAct, nextAct)] += high - lastTs
                elif lastTs < low and high < ts: # Both are out
                    segmentTime[w][(lastAct, nextAct)] += high - low
                
            lastAct = nextAct
            lastTs  = ts
    w = 0
    totalTime = sum([segmentTime[w][k] for k in segmentTime[w].keys() for w in windows])
    #print({w:{k:v/totalTime for k,v in segmentTime[w].items()} for w in windows })
    return segmentTime
    
    
def PlotComparisonLineChart(a, b, ax, xTicks=False, yTicks=False, legend=False):
    if (a.max() - a.min()) == 0 or (b.max() - b.min()) == 0:
        return
    
    d1 = (a - a.min()) / (a.max() - a.min())
    d2 = (b - b.min()) / (b.max() - b.min())
    
    ax.plot([i for i in range(len(d1))], d1, 'grey')
    ax.plot([i for i in range(len(d2))], d2, 'b')
        
    if not xTicks:
        ax.set_xticks([])
    else:
        ax.set_xticks([i for i in range(0,len(d1), int(len(d1)/10))])
    if not yTicks:
        ax.set_yticks([])
    else:
        ax.set_yticks([i/10 for i in range(10)])
        
    diff = [d1[i] - d2[i] for i in range(len(d1))]
    fills = [[diff[0]]]
    last = diff[0]
    for i in range(1, len(diff)):
        if (last > 0 and diff[i] > 0) or (last < 0 and diff[i] < 0):
            fills[-1].append(diff[i])
        else:
            fills.append([diff[i]])            
        last = diff[i]
    
    counter = 0
    for fill in fills:
        r   = [i for i in range(counter, counter+len(fill))]
        rD1 = [d1[i] for i in r]
        rD2 = [d2[i] for i in r]
        if fill[0] > 0:
            ax.fill_between(r, rD1, rD2, color='green', alpha=0.3)
        else:
            ax.fill_between(r, rD1, rD2, color='red', alpha=0.3)
        counter += len(fill)
    
    if legend:
        ax.legend(['ORG', 'SIM'], loc="upper right")
        
def tMes(cb, title):
    t = time()
    ret = cb()
    print(f'{title}: {time()-t}s')
    return ret

def Show(original, processed, figsize=(50,25)):
    origLog = pm4py.read_xes(original)
    proc = pm4py.read_xes(processed)
        
    A = GetActivities(origLog)
    if not A == GetActivities(proc):
        print('The selected logs do not contain the same activities! Is this the correct log combination?')
        exit(1)
    
    segOrig = tMes(lambda: GetActiveSegments(origLog), 'ActSeqOrig')
    segLog  = tMes(lambda: GetActiveSegments(proc), 'ActSeqProc')

    # Detect empty rows / Columns
    Acol = list(A)
    Arow = list(A)
    for i in range(len(A)):
        remRow = True
        remCol = True
        for j in range(len(A)):
            if (A[i], A[j]) in segOrig[0]:
                remRow = False
            if (A[j], A[i]) in segOrig[0]:
                remCol = False
        if remRow:
            Arow.remove(A[i])
        if remCol:
            Acol.remove(A[i])
    
    # Create figure
    fig, axes = plt.subplots(len(Arow), len(Acol), sharex=True, sharey=True)
    fig.set_size_inches(*figsize)

    # Matrix labels    
    #cols = ['Start', 'A', 'B', 'End']     rows = ['Start', 'A', 'B', 'End']
    t = lambda x: ' '.join([s[0:5] + '.' if len(s) > 6 else s for s in str(x).strip().split(' ')])
    for ax, col in zip(axes[0], Acol):
        ax.set_title(t(col), rotation=90)
    for ax, row in zip(axes[:,0], Arow):
        ax.set_ylabel(t(row), rotation=0, labelpad=10, loc='center')
    
    for i in range(len(Arow)):
        for j in range(len(Acol)):
            s = (Arow[i], Acol[j])   
            if s in segOrig[0]:
                d1 = np.array([segOrig[w][s] for w in segOrig])
                d2 = np.array([segLog[w][s] for w in segLog])
                PlotComparisonLineChart(d1, d2, axes[i, j], xTicks=(i==0), yTicks=(j==0),legend = (i==0 and j == 0))
    fig.tight_layout()
    #fig.legend(['ORG', 'SIM'], prop={'size': 6})
    plt.subplots_adjust(hspace=0, wspace=0)
       
    
    # import seaborn as sns
    # # Draw a heatmap with the numeric values in each cell
    # fig, ax = plt.subplots(figsize=(20, 15))
    # sns.heatmap(grouping, annot=True, linewidths=.5, ax=ax)
        
if __name__ == '__main__':
    #main('../logs/log_ResReduced.xes', [os.path.join('../logs', f) for f in os.listdir('../logs') if os.path.isfile(os.path.join('../logs', f)) and f not in ['log_ResReduced.xes', 'log.xes']])
    #main('../logs/log_ResReduced.xes', [os.path.join('../logs', f) for f in os.listdir('../logs') if f.startswith('F') and os.path.isfile(os.path.join('../logs', f)) and f not in ['log_ResReduced.xes', 'log.xes']])
    #main('logs/1_congested.xes', 'tmp.xes')
    
    #Show('logs/log_ResReduced.xes', 'bTemp.xes')
    Show('C:/Users/Alexa/Downloads/BPI_Challenge_2017.xes', 'C:/Users/Alexa/Downloads/BPI_Challenge_2017_CONGESTION.xes', (150, 75))
    
        #  ['../logs/simulated_fairness_log_EQUAL_WORK_ALWAYS.xes',
        #   '../logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_500.xes',
        #   '../logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_500_CONSTANTLY_RESSCHEDULED.xes'])