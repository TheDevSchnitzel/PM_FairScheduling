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
from simulation.objects.enums import FairnessModes
from optimization.model import Model
import networkx as nx

def argsParse():    
	parser = argparse.ArgumentParser()
	parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")
 
	#parser.add_argument('--precision', default=0.0, type=float)
	
	return parser.parse_args()
 
 
 
 
 
 
 
 
def SimulatorFairness_Callback(activeTraces, completedTraces, R, fairnessMode, windows, currentWindow):
    if fairnessMode == FairnessModes.WINDOW:
        resMat_N    = {r:1.0/len(R) for r in R}
        resMat_TIME = {r:1.0/len(R) for r in R}
        
    elif fairnessMode == FairnessModes.BACKLOG:
        BACKLOG_N   = 2
        resMat_N    = {r:0 for r in R}
        resMat_TIME = {r:0 for r in R}
        
        nTotal    = 0
        timeTotal = 0
                
        minTS = windows[max([0, currentWindow - BACKLOG_N])][0]
        maxTS = windows[currentWindow][1]
                
        for trace in completedTraces:
            for data in trace.history:
                if minTS <= data[0] or data[1] <= maxTS:                    
                    resMat_N[data[2]]   += 1
                    nTotal              += 1
                    
                    start = data[0]
                    if data[0] < minTS:
                        start = minTS
                    end = data[1]
                    if maxTS < data[1]:
                        end = maxTS
                    
                    resMat_TIME[data[2]] += end-start
                    timeTotal += end-start
                
        for r in R:
            resMat_N[r] = resMat_N[r] / nTotal
            resMat_TIME[r] = resMat_TIME[r] / timeTotal
        
    print("Fairness callback")
    pass

def SimulatorCongestion_Callback(trace, segment):
    pass

@profile
def SimulatorWindowStart_Callback(activeTraces, P_AtoR, availableResources, time):
    print("MIP callback")
    # # Build MIP
    # model = Model()
    
    # # Solve MIP
    # model.solve()
    
    # model.GetResult()
    
    G = nx.DiGraph()
    for trace in activeTraces:
        if trace.IsWaiting():
            nextActivity = trace.GetNextActivity(SIM_Modes.KNOWN_FUTURE)
            
            G.add_edge('s', 'c' + trace.case, capacity=1)
            
            for r in P_AtoR[nextActivity]:
                G.add_edge('c' + trace.case, r, weight=-1,capacity=1)
            
    for r in availableResources:
        G.add_edge(r, 't', capacity=1)
    
    if len(G.nodes()) != 0:
        M = nx.max_flow_min_cost(G, 's', 't')
        del M['s']
        del M['t']
        for r in availableResources:
            del M[r]
        
        f = lambda x: [res for res, val in x.items() if val > 0]
        return {case[1:]: {'StartTime': time, 'Resource': f(res)[0]} for case, res in M.items() if len(f(res)) == 1}
   
   
    # Temporary simple schedule to test the simulator
    # return {x.case: {'StartTime':x.future[0][2] - 2000, 'Resource':x.future[0][1]} for x in activeTraces if x.IsWaiting()}
    
    return {} # Schedule {caseid:resource}
    
def main():
    args = argsParse()
    
    log = pm4py.read_xes(args.log)
    
    no_events = sum([len(trace) for trace in log])
    windowNumber = 1 * math.ceil(math.sqrt(no_events))
    
    
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
    sim = Simulator(event_dict, eventsPerWindowDict, AtoR, RtoA, bucketId_borders_dict, simulationMode=SIM_Modes.KNOWN_FUTURE, endTimestampAttribute='ts', verbose=True)
    sim.register(SIM_Callbacks.WND_START, SimulatorWindowStart_Callback)
    sim.register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    # sim.register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.run()
    

if __name__ == '__main__':
    main()
