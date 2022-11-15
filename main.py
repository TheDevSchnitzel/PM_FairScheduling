import argparse
import pm4py
import utils.component as component
import utils.extractor as extractor
import utils.frames as frames
import alex
import math
import visualization.viz as viz
from simulation.simulator import Simulator
from simulation.objects.enums import Callbacks as SIM_Callbacks
from simulation.objects.enums import SimulationModes as SIM_Modes
from simulation.objects.enums import TimestampModes
from optimization.model import Model
import networkx as nx
import time
import utils.fairness as Fairness
import json

def argsParse():    
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")

    parser.add_argument('--actDurations', default=None, type=str, help="A dictionary of activities and their duration \'{\'A\': 1}\'")
    #parser.add_argument('--precision', default=0.0, type=float)

    return parser.parse_args()

 
 
 
 
def SimulatorFairness_Callback(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow):
    
    #return Fairness.FairnessEqualWork(R)
    return Fairness.FairnessBacklogFair_WORK(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow, BACKLOG_N=500)
    

def SimulatorCongestion_Callback(trace, segment):
    pass

#@profile
def SimulatorWindowStartScheduling_Callback(activeTraces, P_AtoR, availableResources, simTime, windowDuration, fRatio):
    print("MIP callback")
    
    # These are activity-resource schedulings, where only one resource is able to perform the activity => Hence, no need to add graph nodes
    singleResponsibilitySchedule = {}
    
    t = time.time()
    G = nx.DiGraph()
    
    skipNoTraces = True
    skipNoResources = True
    
    for trace in activeTraces:
        if trace.IsWaiting():
            skipNoTraces = False
            
            nextActivity = trace.GetNextActivity(SIM_Modes.KNOWN_FUTURE)
            nextActivityDuration = trace.GetNextActivityTime(SIM_Modes.KNOWN_FUTURE, TimestampModes.END)
            
            # Either the activity takes more than one window or a duration could not be determined
            if nextActivityDuration > windowDuration or  nextActivityDuration == 0:
                nextActivityDuration = windowDuration
                
                
            G.add_edge('s', 'c' + trace.case, capacity = windowDuration)
            
            # If there is only one resource able to perform the activity, we do not need to integrate it into the flow-graph as there is no other assignment choice
            ableResources = list(P_AtoR[nextActivity])            
            if len(ableResources) == 1:
                singleResponsibilitySchedule[trace.case] = {'StartTime': simTime, 'Resource': ableResources[0] } 
            else:
                for r in ableResources:
                    if fRatio[r] > 0:
                        # Multiply the weights by a large constant factor and round => Doc says floating points can cause issues: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
                        G.add_edge('c' + trace.case, r, weight = -int(1000 * fRatio[r]), capacity = nextActivityDuration)
            
    for r in availableResources:
        skipNoResources = False
        G.add_edge(r, 't', capacity = windowDuration)
    
    #print(f"    -> Construction: {time.time() - t}s")
    #print(G.edges.data())
    print(f"    -> Nodes: {len(G.nodes())}")
    if len(G.nodes()) != 0 and not skipNoTraces and not skipNoResources:
        t = time.time()
        M = nx.max_flow_min_cost(G, 's', 't')
        #print(M)
        #print(f"    -> Solve: {time.time() - t}s")
        
        t = time.time()
        del M['s']
        del M['t']
        for r in availableResources:
            del M[r]
        
        f = lambda x: [res for res, val in x.items() if val > 0]
        ret =  {case[1:]: {'StartTime': simTime, 'Resource': f(res)[0]} for case, res in M.items() if len(f(res)) > 0}
        
        #print(f"    -> Post: {time.time() - t}s")
        return {**ret, **singleResponsibilitySchedule}
   
   
    # Temporary simple schedule to test the simulator
    # return {x.case: {'StartTime':x.future[0][2] - 2000, 'Resource':x.future[0][1]} for x in activeTraces if x.IsWaiting()}
    
    return {} # Schedule {caseid:resource}
    
def main():
    args = argsParse()
    
    log = pm4py.read_xes(args.log)
    
    no_events = sum([len(trace) for trace in log])
    windowNumber = 100 * math.ceil(math.sqrt(no_events))
    print(f"Number of windows: {windowNumber}")
    
    # Convert XES-Events into dict {'act', 'ts', 'res', 'single', 'cid'}
    event_dict = extractor.event_dict(log, res_info=True)
    
    # Pairs of events directly following each other, events triggering others (preceed them), events releasing others (follow them)
    pairs, triggers, releases = extractor.trig_rel_dicts(log, method='df')
    
    # All activities, resources and DFG-Segments as sets
    A_set, R_set, S_set, AtoR, RtoA = component.components(event_dict, pairs, res_info=True)
    

    print('Computing frames, partitioning events into frames')
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, windowWidth)
    eventsPerWindowDict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, windowWidth) # WindowID: [List of EventIDs] , EventID: WindowID
        
    # Visualize the events over time with window borders
    # viz.WindowBorders(log, windowNumber)
    # alex.GetResourceLoadDistribution(A_set, R_set, S_set, event_dict, triggers, bucketId_borders_dict, id_frame_mapping, pairs, res_info=True, act_selection='all', res_selection='all')
    # alex.GetResourceTimeDistribution(R_set, event_dict, bucketId_borders_dict, id_frame_mapping, pairs, triggers)
    
    
    # Simulation -> Callback at the beginning / end of each window
    sim = Simulator(event_dict, eventsPerWindowDict, AtoR, RtoA, bucketId_borders_dict, simulationMode=SIM_Modes.KNOWN_FUTURE, endTimestampAttribute='ts', verbose=False)
    sim.Register(SIM_Callbacks.WND_START_SCHEDULING, SimulatorWindowStartScheduling_Callback)
    sim.Register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    # sim.register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.Run()
    sim.ExportSimulationLog('logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_500.xes')

if __name__ == '__main__':
    main()
