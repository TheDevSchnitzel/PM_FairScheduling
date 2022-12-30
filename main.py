import argparse
import json
import math
import multiprocessing
import signal
import time
from multiprocessing import Pool
import uuid
import threading

import pm4py

import utils.congestion as Congestion
import utils.extractor as extractor
import utils.fairness as Fairness
import utils.frames as frames
import utils.optimization as Optimization
from utils.network.client import Client
from utils.network.enums import Callbacks as ClientCallbacks
from predictor.predictor import PredictorService
from simulation.objects.enums import Callbacks as SIM_Callbacks
from simulation.objects.enums import OptimizationModes, SchedulingBehaviour
from simulation.objects.enums import SimulationModes as SIM_Modes
from simulation.objects.enums import TimestampModes
from simulation.simulator import Simulator
from utils.activityDuration import EventDurationsByMinPossibleTime
import pickle
import traceback

G_KnownActivityDurations = {}
scriptArgs = None
simulator  = None
predictor  = None
predClient = None
predClientLocks = {}

def kernel_panic(signum, frame):
    global simulator
    global scriptArgs
    global predictor
    global predClient

    if simulator is not None:
        simulator.HandleSimulationAbort()
        simulator.ExportSimulationLog(scriptArgs.out, exportSimulatorStartEndTimestamp=False)
    
    if predictor is not None:
        predictor.StopService()

    if predClient is not None:
        predClient.Stop()

    exit(1)    
signal.signal(signal.SIGINT, kernel_panic)


def argsParse(cmdParameterLine = None): 
    global scriptArgs   
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")
    parser.add_argument('-o', '--out', default='logs/simLog.xes', type=str, help="The path to which the simulated event-log will be exported")

    parser.add_argument('--actDurations', default=None, type=str, help="A dictionary of activities and their duration \'{\'A\': 1}\'")
    parser.add_argument('--SimMode', default='known_future',choices=['known_future','prediction'], type=str, help="")
    parser.add_argument('--SchedulingBehaviour', default='clear',choices=['clear','keep'], type=str, help="Specify whether scheduling assignments that could not be carried out before the next scheduling callback should be kept or cleared")
            
    # Fairness parameters
    parser.add_argument('-F', '--Fair', default=None, choices=['W','T'], type=str, help="W: Amount of work / T: Time spent working")
    parser.add_argument('--FairnessBacklogN', default=50, type=int, help="Number of passed windows to consider for fairness calculations")
    
    # Congestion parameters
    parser.add_argument('-C', '--Congestion', default=None, choices=['N','T'], type=str, help="N: Number of cases in segment / T: Time spent in segment")
    parser.add_argument('--CongestionBacklogN', default=50, type=int, help="Number of passed windows to consider for calculations")
    
    # Multi-Simulation mode
    parser.add_argument('-M', '--MultiSimulation', default=None, type=str, help="Path to config file for running multiple simulations in parallel, containing commandline parameters with each line being one experiment")
    parser.add_argument('--MultiSimCores', default=int(multiprocessing.cpu_count() / 2), type=int, help="Amount of cores/processes to use for computation - Python can behave weird if the number is close to the amount of available logical cores")

    # Predictor parameters
    parser.add_argument('--PredictorPort', default=5050, type=int, help="Port of the server handling predictions")
    parser.add_argument('--PredictorHost', default=None, type=str, help="IP address of the server host handling predictions")
    parser.add_argument('--PredictorModelNextAct', default=None, type=str, help="Pretrained .h5 TF model used for predictions or the model name if connecting to a remote predictor service")
    parser.add_argument('--PredictorModelActDur', default=None, type=str, help="Pretrained .h5 TF model used for predictions or the model name if connecting to a remote predictor service")
    parser.add_argument('--PredictorStandalone', default=False, action='store_true', help="Do not start the simulator but only thy predictor servcie as a standalone")
    
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    
    
    # Get args either from CMD or from MultiSim.cfg string
    if cmdParameterLine is None:
        argData = parser.parse_args()
    else:
        argData = parser.parse_args(cmdParameterLine.split())

    
    # Check for pre-defined activity durations
    if argData.actDurations is not None:
        print(argData.actDurations)
        global G_KnownActivityDurations
        G_KnownActivityDurations = json.loads(argData.actDurations)
    
    # Ensure proper multiprocessing safety (Python seems to act odd on too many simultaneous processes)
    if argData.MultiSimCores > int(multiprocessing.cpu_count() / 2):
        descision = input('Using more than half of the virtual cores available might lead to instability due to the nature of python multiprocessing! Continue [y/n]?')
        if descision not in ['y','Y','yes','Yes']:
            exit(0)

    # Check whether a model is specified if predictions are to be used
    if (argData.PredictorModelNextAct is None or argData.PredictorModelActDur is None) and (argData.SimMode == 'prediction' or argData.PredictorStandalone):
        print('NO MODEL SPECIFIED! - You specified to use prediction mode or want to start a standalone predictor, make sure to provide a prediction model via --PredictorModelNextAct and --PredictorModelActDur')
        exit(0)
            
    scriptArgs = argData
    return argData

def ConvertArguments(args):
    # Read the config to set up the simulator
    if args.SimMode == 'known_future':
        simMode = SIM_Modes.KNOWN_FUTURE
    elif args.SimMode == 'prediction':
        simMode = SIM_Modes.PREDICTED_FUTURE
    else:
        raise('No simulation mode specified!')
    
    if args.Fair is not None and args.Congestion is not None:
        optMode = OptimizationModes.BOTH
    elif args.Fair is not None:
        optMode = OptimizationModes.FAIRNESS
    elif args.Congestion is not None:
        optMode = OptimizationModes.CONGESTION
    else:
        raise('No optimization mode specified!')
      
    if args.SchedulingBehaviour == 'clear':
        schedBehaviour = SchedulingBehaviour.CLEAR_ASSIGNMENTS_EACH_WINDOW
    elif args.SchedulingBehaviour == 'keep':
        schedBehaviour = SchedulingBehaviour.KEEP_ASSIGNMENTS
    else:
        raise('No simulation mode specified!')
    
    return simMode, optMode, schedBehaviour





def SimulatorFairness_Callback(simulatorState):
    global scriptArgs       
        
    if scriptArgs.Fair == "W":
        return Fairness.FairnessBacklogFair_WORK(simulatorState, BACKLOG_N=scriptArgs.FairnessBacklogN)
    elif scriptArgs.Fair == "T":
        return Fairness.FairnessBacklogFair_TIME(simulatorState, BACKLOG_N=scriptArgs.FairnessBacklogN)

def SimulatorCongestion_Callback(simulatorState):
    global scriptArgs

    if scriptArgs.Congestion == "N":
        return Congestion.GetProgressByWaitingNumberInFrontOfActivity(simulatorState, scriptArgs.CongestionBacklogN)
    elif scriptArgs.Congestion == "T":
        return Congestion.GetProgressByWaitingTimeInFrontOfActivity(simulatorState, scriptArgs.CongestionBacklogN)

def SimulatorWindowStartScheduling_Callback(simulatorState, schedulingReadyResources, fRatio, cRatio):
    #return Optimization.SimulatorTestScheduling(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode)
    return Optimization.OptimizeActiveTraces(simulatorState, schedulingReadyResources, fRatio, cRatio)






########################################################
#############                              #############
##########      THREAD SENSITIVE METHODS      ##########
#############                              #############
########################################################
def SimulatorPredictionNextAct_Callback(trace):
    return SimulatorPredictionCommHandling('next_activity', trace)

def SimulatorPredictionActDur_Callback(trace, currentActivity=False):
    return float(SimulatorPredictionCommHandling('duration', trace, currentActivity))

def SimulatorPredictionCommHandling(task, trace,currentActivity=False):
    global scriptArgs
    global predClient
    global predClientLocks
    
    id   = uuid.uuid4()
    lock = threading.Lock()
    predClientLocks[id] = {'Lock': lock, 'Result': None}
    
    # Acquire the lock, such that it isn't available anymore
    lock.acquire()

    # Messages are sent async, further the predictor service does not need to process the requests in order
    predClient.SendMessage(pickle.dumps({'Task': task, 'Trace': trace, 'ID': id, 'CurrentActivity': currentActivity}))

    # Try to acquire again => Forces thread to wait until the lock is released in the 'PredictorAnswer_Callback' method
    
    print(0)
    lock.acquire()    
    print(3)
    ret = predClientLocks[id]['Result']
    del predClientLocks[id]
    return ret

def PredictorAnswer_Callback(msg):
    """Once an answer from the prediction service is received, update the according waiting thread.
    This method itself is called from the hanlder-thread of the predictor service, therfore a different thread than the simulation"""
    global predClientLocks

    print(1)
    data = pickle.loads(msg)
    predClientLocks[data['ID']]['Result'] = data['Result']    
    predClientLocks[data['ID']]['Lock'].release()
    print(2)



####################################
#############          #############
##########      MAIN      ##########
#############          #############
####################################
def Run(args):    
    if type(args) == str:
        args = argsParse(args)

    log = pm4py.read_xes(args.log)
    
    no_events = sum([len(trace) for trace in log])
    windowNumber = 100 * math.ceil(math.sqrt(no_events))
    print(f"Number of windows: {windowNumber}")
    
    # Convert XES-Events into dict {'act', 'ts', 'res', 'single', 'cid', 'lc'}
    event_dict = extractor.event_dict(log, res_info=True)
    
    # Pairs of events directly following each other, events triggering others (preceed them), events releasing others (follow them)
    # pairs, triggers, releases = extractor.trig_rel_dicts(log, method='df')
    
    print('Computing frames, partitioning events into frames')
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, windowWidth)
    eventsPerWindowDict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, windowWidth) # WindowID: [List of EventIDs] , EventID: WindowID
      
    # Read the config to set up the simulator
    simMode, optMode, schedBehaviour = ConvertArguments(args)

    # Simulation -> Callback at the beginning / end of each window
    sim = Simulator(log, eventsPerWindowDict, bucketId_borders_dict, 
                    simulationMode      = simMode,
                    optimizationMode    = optMode,
                    schedulingBehaviour = schedBehaviour,
                    verbose=args.verbose)
    
    global simulator
    simulator = sim
    
    sim.Register(SIM_Callbacks.WND_START_SCHEDULING, SimulatorWindowStartScheduling_Callback)
    sim.Register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    sim.Register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.Register(SIM_Callbacks.CALC_EventDurations, lambda x,y: EventDurationsByMinPossibleTime(x,y)) # Something like EventDurationsByLifecycle?

    sim.Register(SIM_Callbacks.PREDICT_NEXT_ACT, SimulatorPredictionNextAct_Callback)
    sim.Register(SIM_Callbacks.PREDICT_ACT_DUR,  SimulatorPredictionActDur_Callback)

    sim.Initialize()
    sim.Run()
    sim.ExportSimulationLog(args.out)
    #sim.ExportSimulationLog('logs/simulated_congestion_log_WAITING_TRACE_COUNT.xes')


def main():
    global predictor
    global predClient
    
    args = argsParse()

    # Is there a remote prediction service? -> If not set up a local one
    if args.PredictorHost is None and (args.PredictorModelNextAct is not None and args.PredictorModelActDur is not None) and (args.SimMode == 'prediction' or args.PredictorStandalone):
        print('Starting predictor service')
        predictor = PredictorService(None, args.PredictorPort, args.PredictorModelNextAct, args.PredictorModelActDur, verbose=args.verbose)
        predictor.StartService(args.PredictorStandalone)
    
    if not args.PredictorStandalone:
        if args.SimMode == 'prediction':
            # Connect to the predictor service
            predClient = Client(verbose=args.verbose)
            predClient.Register(ClientCallbacks.MESSAGE_RECEIVED, PredictorAnswer_Callback)
            predClient.Connect(args.PredictorHost, args.PredictorPort, timeout=2)
        
        # Do we run a single simulation or multiple in parallel?
        if args.MultiSimulation is None:
            Run(args)
        else:
            argList = []
            with open(args.MultiSimulation, "r") as f:
                for x in f.readlines():
                    cmd = x.replace('\n','').strip()
                    if cmd != "":
                        argList.append(cmd)

            with Pool(max(1, args.MultiSimCores)) as p:
                p.map(Run, argList)
    

if __name__ == '__main__':
    try:
        main()
    except:
        traceback.print_exc()
        kernel_panic(None, None)
