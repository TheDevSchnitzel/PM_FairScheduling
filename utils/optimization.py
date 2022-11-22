
import time
import networkx as nx


from simulation.objects.enums import SimulationModes as SIM_Modes
from simulation.objects.enums import TimestampModes, OptimizationModes


def OptimizeActiveTraces(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode):
    # These are activity-resource schedulings, where only one resource is able to perform the activity => Hence, no need to add graph nodes
    singleResponsibilitySchedule = {}
        
    G = nx.DiGraph()
            
    skipNoTraces = True
    skipNoResources = True
    totalActivityDuration = 0
        
    for trace in activeTraces:
        if trace.IsWaiting():            
            nextActivity = trace.GetNextActivity(SIM_Modes.KNOWN_FUTURE)
            nextActivityDuration = trace.GetNextActivityTime(SIM_Modes.KNOWN_FUTURE, TimestampModes.END)
            
            # Either the activity takes more than one window or a duration could not be determined
            if nextActivityDuration > windowDuration or nextActivityDuration == 0:
                nextActivityDuration = windowDuration
                            
            # If there is only one resource able to perform the activity, we do not need to integrate it into the flow-graph as there is no other assignment choice
            ableResources = list(P_AtoR[nextActivity])            
            if len(ableResources) == 1:
                singleResponsibilitySchedule[trace.case] = {'StartTime': simTime, 'Resource': ableResources[0] } 
            else:
                skipNoTraces = False
                G.add_edge('s', 'c' + trace.case, capacity = windowDuration)
                totalActivityDuration += nextActivityDuration
                
                for r in ableResources:
                    if optimizationMode == OptimizationModes.FAIRNESS and fRatio[r] > 0:
                        # Multiply the weights by a large constant factor and round => Doc says floating points can cause issues: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
                        G.add_edge('c' + trace.case, r, weight = -int(1000 * fRatio[r]), capacity = int(nextActivityDuration) + 1)
                    elif optimizationMode == OptimizationModes.CONGESTION and cRatio[nextActivity] > 0:
                        G.add_edge('c' + trace.case, r, weight = -int(1000 * cRatio[nextActivity]), capacity = int(nextActivityDuration) + 1)
                    elif optimizationMode == OptimizationModes.BOTH:
                        # ??? Normalizing, Scaling and weighting cRatio and fRatio ????
                        continue
            
    for r in availableResources:
        skipNoResources = False
        G.add_edge(r, 'd', capacity = windowDuration)
    
    # Collect multi-flows
    G.add_edge('d', 't', capacity = totalActivityDuration)
    
    #print(G.edges.data())
    if not skipNoTraces and not skipNoResources:
        #print(f"    -> Nodes: {len(G.nodes())}")
        M = nx.max_flow_min_cost(G, 's', 't')
        #print(M)
        #print(f'Cost: {nx.cost_of_flow(G, M)}')
        
        del M['s']
        del M['t']
        for r in availableResources:
            del M[r]
        
        f = lambda x: [res for res, val in x.items() if val > 0]
        ret =  {case[1:]: {'StartTime': simTime, 'Resource': f(res)[0]} for case, res in M.items() if len(f(res)) > 0}
        
        schedule = {**ret, **singleResponsibilitySchedule}
        #print(ret)
        return schedule
   
   
    # Temporary simple schedule to test the simulator
    # return {x.case: {'StartTime':x.future[0][2] - 2000, 'Resource':x.future[0][1]} for x in activeTraces if x.IsWaiting()}
    
    return singleResponsibilitySchedule # Schedule {caseid:resource}