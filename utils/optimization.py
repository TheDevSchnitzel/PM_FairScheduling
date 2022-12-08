
import time
import networkx as nx
from simulation.objects.enums import OptimizationModes
import random

def SimulatorTestScheduling(simulatorState, availableResources, fRatio, cRatio):
    """Schedule exactly like in the original log to see how it's going - Test this with scheduling every single timestep, not window based!"""
    
    # Parameter extraction
    activeTraces     = simulatorState['ActiveTraces']

    
    data = [(trace.case, trace.future[0][1], trace.future[0][2]) for trace in activeTraces if trace.IsWaiting()]
    data = sorted(data, key=lambda x: x[2]) #Sort by ts
    
    sched = {}
    resUsed = []
    for (case, res, ts) in data:
        if res not in resUsed:
            sched[case] = {'StartTime': ts, 'Resource': res}
            resUsed.append(res)
    return sched
        
        

def OptimizeActiveTraces(simulatorState, availableResources, fRatio, cRatio, timeAwareButNotOptimal=False):
    # Parameter extraction
    activeTraces     = simulatorState['ActiveTraces']
    AtoR             = simulatorState['AtoR']
    simTime          = simulatorState['CurrentTimestep']
    windowDuration   = simulatorState['CurrentWindowDuration']
    optimizationMode = simulatorState['OptimizationMode']
    simulationMode   = simulatorState['SimulationMode']
    timestampMode    = simulatorState['TimestampMode']
    
    # These are activity-resource schedulings, where only one resource is able to perform the activity => Hence, no need to add graph nodes
    singleResponsibilitySchedule = {}
        
    G = nx.DiGraph()
                        
    skipNoTraces = True
    skipNoResources = True
    totalActivityDuration = 0
    
    if timeAwareButNotOptimal:
        startArcCapacity = windowDuration
    else:
        startArcCapacity = 1
        
    for trace in activeTraces:
        # Skip traces that are still processing
        if not trace.IsWaiting():
            continue
        
        nextActivity = trace.GetNextActivity(simulationMode)
        nextActivityDuration = trace.GetNextActivityTime(simulationMode, timestampMode)
        
        # Either the activity takes more than one window or a duration could not be determined
        if nextActivityDuration > windowDuration or nextActivityDuration == 0:
            nextActivityDuration = windowDuration
        
        # For a MIP to be solvable as a flownetwork (LP-Relax.), the coeff. matrix needs to be TU! => Not given if capacity not binary
        if not timeAwareButNotOptimal:
            nextActivityDuration = 0
                        
        # If there is only one resource able to perform the activity, we do not need to integrate it into the flow-graph as there is no other assignment choice
        ableResources = AtoR[nextActivity]
        if len(ableResources) == 1:
            singleResponsibilitySchedule[trace.case] = {'StartTime': simTime, 'Resource': ableResources[0] } 
        else:
            skipNoTraces = False
            G.add_edge('s', 'c' + trace.case, capacity = startArcCapacity) # Factor smaller than cRatio/fRatio, only steer
            totalActivityDuration += int(nextActivityDuration) + 1
            
            for r in ableResources:
                if optimizationMode == OptimizationModes.FAIRNESS and fRatio[r] > 0:
                    # Multiply the weights by a large constant factor and round => Doc says floating points can cause issues: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
                    G.add_edge('c' + trace.case, r, weight = -int(100000 * fRatio[r]), capacity = int(nextActivityDuration) + 1)
                elif optimizationMode == OptimizationModes.CONGESTION:
                    s = (None, nextActivity)
                    if len(trace.history) > 0:
                        s = (trace.history[-1][3][0], nextActivity)
                    if cRatio[s] > 0:
                        G.add_edge('c' + trace.case, r, weight = -int(100000 * cRatio[s]), capacity = int(nextActivityDuration) + 1)
                elif optimizationMode == OptimizationModes.BOTH:
                    # ??? Normalizing, Scaling and weighting cRatio and fRatio ????
                    continue
            
    for r in availableResources:
        skipNoResources = False        
        if timeAwareButNotOptimal:
            G.add_edge(r, 'd', capacity = windowDuration)
        else:
            G.add_edge(r, 't', capacity = 1)
    
    # Collect multi-flows if not optimal
    if timeAwareButNotOptimal:
        G.add_edge('d', 't', capacity = totalActivityDuration)
    
    if not skipNoTraces and not skipNoResources:
        return {**ResolveNetwork(G, availableResources, simTime, timeAwareButNotOptimal), **singleResponsibilitySchedule}
          
    return singleResponsibilitySchedule # Schedule {caseid:resource}

def ResolveNetwork(G, availableResources, simTime, timeAwareButNotOptimal):
    M = nx.max_flow_min_cost(G, 's', 't')
    
    # Remove unecessary nodes
    del M['s']
    del M['t']    
    for r in availableResources:
        del M[r]
    if timeAwareButNotOptimal:
        del M['d']
    
    ## Extract the scheduled flows
    # Use lambda to exclude assignments that are floating point errors
    f = lambda x: [res for res, val in x.items() if val > 0.1]
    
    # In case multiple assignments exist, we are in a time aware scenario which is not guaranteed to be optimal, hence => pick one of the assigned resources randomly
    return {case[1:]: {'StartTime': simTime, 'Resource': random.choice(f(res))} for case, res in M.items() if len(f(res)) > 0}
