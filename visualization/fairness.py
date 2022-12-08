import pm4py
import matplotlib.pyplot as plt
import pandas as pd

from utils.extractor import ts_to_int as GetIntTs

def GetActivityResourceMapping(log):
    actResFrequency = {}
    actResTime = {}
    resFreq = {}
    resTime = {}
    
    for trace in log:
        n = len(trace)
        for i in range(n):
            event = trace[i]
            act = event['concept:name']
            res = event['org:resource']
            ts  = GetIntTs(event['time:timestamp'])
                        
            if res in resFreq:
                resFreq[res] += 1
            else: 
                resFreq[res] = 1
                resTime[res] = 0
                            
            if act in actResFrequency:
                if res in actResFrequency[act]:
                    actResFrequency[act][res] += 1
                else:
                    actResFrequency[act][res] = 1
                    actResTime[act][res]      = 0
            else:
                actResFrequency[act] = {res: 1}
                actResTime[act]      = {res: 0}
                
            if i > 0:
                prevTS = GetIntTs(trace[i-1]['time:timestamp'])
                duration = ts - prevTS
                actResTime[act][res] += duration
                resTime[res]         += duration
    
    R = list(resFreq.keys())
    R.sort()
    A = list(actResFrequency.keys())
    A.sort()
    sortedAtoR = {a: sorted(list(set([r for r in actResTime[a].keys()]))) for a in A}
    
    
    sumTime = sum([resTime[r] for r in R])
    sumFreq = sum([resFreq[r] for r in R])
    
    df1 = pd.DataFrame(data={
        'Resource': R, 
        'Total-Activities': [resFreq[r] for r in R], 
        'Relative-Activities': [resFreq[r] / sumFreq for r in R],
        'Total-Time': [resTime[r] for r in R], 
        'Relative-Time': [resTime[r] / sumTime for r in R],
    })    
                
    df2 = pd.DataFrame(data={
        'Activity': [a for a in A for _ in range(len(actResTime[a]))], 
        'Resource': [r for a in A for r in sortedAtoR[a]], 
        'Total-Activities': [actResFrequency[a][r] for a in A for r in sortedAtoR[a]], 
        'Relative-Activities': [actResFrequency[a][r] / sumFreq for a in A for r in sortedAtoR[a]],
        'Total-Time': [actResTime[a][r] for a in A for r in sortedAtoR[a]], 
        'Relative-Time': [actResTime[a][r] / sumTime for a in A for r in sortedAtoR[a]],
    })    
    return df1, df2                


def Show(originalLogPath, simulatedLogPath):
    simulatedLog = pm4py.read_xes(simulatedLogPath)
    originalLog = pm4py.read_xes(originalLogPath)

    dfOriginal, dfO2  = GetActivityResourceMapping(originalLog)
    dfSimulated, dfS2 = GetActivityResourceMapping(simulatedLog)


    def GetValue(df, r, a, col):
        val = df.loc[(df.Resource == r) & (df.Activity == a)][col]
        if len(val) == 0:
            return 0
        else:    
            return val.values[0]
        
    # plot with various axes scales - https://matplotlib.org/3.1.1/gallery/pyplots/pyplot_scales.html#sphx-glr-gallery-pyplots-pyplot-scales-py
    plt.figure(figsize=(35,60))
    fig, axes = plt.subplots(2, 2)

    def PlotChart(title, df, col, plotX, plotY):
        A = sorted(list(set(df['Activity'])))
        R = sorted(list(set(df['Resource'])))
                
        df = pd.DataFrame([[str(r)[0:3]] + [GetValue(df, r, a, col) for a in A] for r in R], columns=['Resource'] + A)
        
        # plot data in stack manner of bar type
        df.plot(x='Resource', kind='bar', stacked=True, title=title, ax=axes[plotX, plotY], legend=False)
        plt.title(title)
        plt.grid(False)

    PlotChart('Original - Time', dfO2, 'Relative-Time', 0, 0)
    PlotChart('Original - Work', dfO2, 'Relative-Activities', 0, 1)

    PlotChart('Simulated - Time', dfS2, 'Relative-Time', 1, 0)
    PlotChart('Simulated - Work', dfS2, 'Relative-Activities', 1, 1)

    fig.legend(sorted(list(set(dfO2['Activity']))), prop={'size': 6})

    # Set padding between subplots
    plt.subplots_adjust(hspace=0.90, wspace=0.35)
    plt.show()