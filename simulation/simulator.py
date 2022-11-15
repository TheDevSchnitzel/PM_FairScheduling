from distutils.log import error
import time
from .objects.traceInstance import Trace
from .objects.enums import Callbacks, TimestampModes, SimulationModes
from datetime import datetime, timezone
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.conversion.log import converter as log_converter
import pandas as pd

class Simulator:
    
    def __init__(self, event_dict, eventsPerWindowDict, AtoR, RtoA, windows, simulationMode, startTimestampAttribute=None, endTimestampAttribute=None, verbose=False):
        self.P_Events = event_dict
        self.P_EventsPerWindowDict = eventsPerWindowDict
        self.P_AtoR = AtoR
        self.P_RtoA = RtoA
        self.P_Windows = windows
        self.P_Verbose = verbose
        self.P_SimulationMode = simulationMode
        
        self.R = [r for r in RtoA.keys()]
        
        self.completedTraces = list()
        self.callbacks = { x: None for x in Callbacks }
        
        self.traceCount = 0        
        self.traces = []
        
        
        # Determine what type of timestamps are available for the simulation
        if startTimestampAttribute is None and endTimestampAttribute is None:
            raise Exception("At least one of the parameters 'startTimestampAttribute' and 'endTimestampAttribute' needs to be set!")
        elif startTimestampAttribute is not None and endTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.BOTH
            self.TimestampAttribute = (startTimestampAttribute, endTimestampAttribute)
        elif startTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.START
            self.TimestampAttribute = startTimestampAttribute
        elif endTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.END
            self.TimestampAttribute = endTimestampAttribute
        
        # Build trace objects from the event data
        self.GenerateTraces()
        
        # Get resources that only perform activities that no other resource can perform
        self.LonelyResources = self.__GetLonelyResources()

    def __vPrint(self, msg):
        if self.P_Verbose:
            print(msg)
            
    def __GetLonelyResources(self):
        """Lonely resources are carrying out activities without any other resource taking part in the same activity
        They have to be treated differently for e.g. fairness calculations"""
        lonelyResources = []
        
        for _, rSet in self.P_AtoR.items():
            rList = list(rSet)
            if len(rList) == 1:
                if rList[0] not in lonelyResources:
                    lonelyResources.append(rList[0])
            else:
                notLonely = [r for r in lonelyResources if r in rList]
                lonelyResources = list(set(lonelyResources) - set(notLonely))
        return lonelyResources

    def Register(self, callbackType, callback):
        self.callbacks[callbackType] = callback
        
    def GenerateTraces(self):
        eventTraces = {cid:[] for cid in set([e['cid'] for _, e in self.P_Events.items()])}
        
        # Build the event traces
        for _, e in self.P_Events.items():
            eventTraces[e['cid']].append(e)
        
        # Sort events in traces by timestamp
        for cid in eventTraces.keys():
            if self.TimestampMode == TimestampModes.START or self.TimestampMode == TimestampModes.END:
                eventTraces[cid].sort(key=lambda e: e[self.TimestampAttribute])
                self.traces.append(Trace(str(cid), [(e['act'], e['res'], e[self.TimestampAttribute]) for e in eventTraces[cid]]))
            else:
                eventTraces[cid].sort(key=lambda e: e[self.TimestampAttribute[0]])
                self.traces.append(Trace(str(cid), [(e['act'], e['res'], e[self.TimestampAttribute[0]], e[self.TimestampAttribute[1]]) for e in eventTraces[cid]]))
        
        self.traceCount = len(self.traces)
        
    def GetIdleResources(self):
        """Get resources currently not performing any activity and are free for scheduling"""
        return []
    
    def GetNewlyBeginningTraces(self, windowLower, windowUpper):
        activeTraces = [x for x in self.traces if x.NextEventInWindow(windowLower, windowUpper)]
        
        # Remove newly active traces from To-Do list
        for x in activeTraces:
            self.traces.remove(x)
            
        return activeTraces
    
    # Print iterations progress
    def printProgressBar(self, iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            length      - Optional  : character length of bar (Int)
            fill        - Optional  : bar fill character (Str)
            printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
        # Print New Line on Complete
        if iteration == total: 
            print()
            
    def Run(self):
        currentWindow = -1
        currentWindowLower = self.P_Windows[0][0]
        currentWindowUpper = self.P_Windows[0][1]
        currentWindowDuration = currentWindowUpper - currentWindowLower
        simulatedTimestep = currentWindowLower
        
        simStart = time.time()
        self.__vPrint("Simulation started at %s" % (datetime.now().strftime("%d/%m/%Y, %H:%M:%S")))
        self.__vPrint(f"    Traces: {self.traceCount}")
                
        # Create a list of initially active traces
        activeTraces = self.GetNewlyBeginningTraces(currentWindowLower, currentWindowUpper)
        
        # Initially all resources are available for the full window time 
        availableResources = {r: currentWindowUpper - currentWindowLower for r in self.R}
        
        # An empty schedule
        schedule = {}
        
        while len(self.completedTraces) != self.traceCount:            
            # If a new window has begun, run the planning again
            if currentWindowUpper < simulatedTimestep or currentWindow == -1:
                currentWindow += 1
                
                if currentWindow < len(self.P_Windows):
                    currentWindowLower = self.P_Windows[currentWindow][0]
                    currentWindowUpper = self.P_Windows[currentWindow][1]
                else:
                    currentWindowLower = simulatedTimestep
                    currentWindowUpper = simulatedTimestep + (self.P_Windows[0][1] - self.P_Windows[0][0])
                    self.P_Windows[currentWindow] = (currentWindowLower, currentWindowUpper)
                    
                currentWindowDuration = currentWindowUpper - currentWindowLower
                self.__vPrint(f' ### New Window {currentWindow} - {datetime.fromtimestamp(currentWindowLower)} <==> {datetime.fromtimestamp(currentWindowUpper)} ###')
                
                # Calculate fairness ratio - { r: x \in [0, 1] for r in R }
                fRatio = None
                if self.callbacks.get(Callbacks.CALC_Fairness) is not None:
                    fTimeStart = time.time()
                    fRatio = self.callbacks.get(Callbacks.CALC_Fairness)(activeTraces, self.completedTraces, self.LonelyResources, self.R, self.P_Windows, currentWindow)
                    self.__vPrint(f"    -> Fairness-Callback took: {time.time() - fTimeStart}s")
                
                # Calculate congestion ratio - { per segment? }
                #if self.callbacks[Callbacks.CALC_Congestion] is not None:
                #    cRatio = self.callbacks[Callbacks.CALC_Congestion](trace, segment)
                
                # Start new traces that arrive in this window
                activeTraces = activeTraces + self.GetNewlyBeginningTraces(currentWindowLower, currentWindowUpper)
                
                # Add resources which will become free during this window to be scheduled
                for trace in activeTraces:
                    if trace.HasRunningActivity():
                        remTime = trace.GetRemainingActivityTime(self.TimestampMode, simulatedTimestep) 
                        if remTime < currentWindowDuration:
                            availableResources[trace.currentAct[1]] = currentWindowDuration - remTime
                
                # Call to get the new schedule (most likely a MIP scheduling)
                cbScheduling = self.callbacks.get(Callbacks.WND_START_SCHEDULING)
                if cbScheduling is not None:
                    fTimeStart = time.time()
                    
                    # Get traces without a current schedule (no need to double schedule traces if they have already been scheduled)
                    unscheduledTraces = [x for x in activeTraces if x.case not in schedule]
                    
                    if len(unscheduledTraces) > 0:
                        # Perform the scheduling callback (Leave it to the Sim-User to provide a way to calculate the schedule)
                        newSchedule = cbScheduling(unscheduledTraces, self.P_AtoR, availableResources, simulatedTimestep, currentWindowUpper-currentWindowLower, fRatio)
                        
                        # Merge schedule dicts (Trace-ID is key, no duplicates ;) )
                        schedule = {**schedule, **newSchedule}
                                        
                        self.__vPrint(f"    -> WND_START-Callback took: {time.time() - fTimeStart}s")

                
                
            # Do the simulation that has to be done at each timestep (second???)
            # Apply pre-calculated schedule
            # Begin new / end old traces
            
            # Speedup by trying to skip unimportant timesteps in the simulation
            minRemainingTime = currentWindowUpper - simulatedTimestep
            
            # First stop all activities ending in this timestep
            for trace in activeTraces:
                if trace.HasRunningActivity():
                    remainingTime = trace.GetRemainingActivityTime(self.TimestampMode, simulatedTimestep)
                    if remainingTime <= 0:
                        trace.EndCurrentActivity(simulatedTimestep)
                            
                        # Return the now free resource to the resource pool (Resource actually used by newest event in history of trace)
                        availableResources[trace.history[-1][2]] = currentWindowUpper - simulatedTimestep
                        self.__vPrint(f"    -> Trace '{trace.case}' has ended freeing res '{trace.history[-1][2]}' at simtime {simulatedTimestep}")
                            
                        if trace.HasEnded():
                            activeTraces.remove(trace)
                            self.completedTraces.append(trace)
                    elif remainingTime < minRemainingTime:
                        minRemainingTime = remainingTime
                        
                # self.vPrint(f"    -> Trace '{trace.case}', Waiting: '{trace.IsWaiting()}', Running: '{trace.HasRunningActivity()}'")
                            
            # As the previous step released new resources, now start new activities that might need them (double assigned resources)
            for trace in activeTraces:
                if trace.IsWaiting():
                    # It the trace on the schedule?
                    traceSched = schedule.get(trace.case)
                    if traceSched is not None and traceSched['StartTime'] <= simulatedTimestep:
                        if traceSched['Resource'] in availableResources:
                            self.__vPrint(f"    -> Trace '{trace.case}' about to start on res '{traceSched['Resource']}' at simtime {simulatedTimestep}")
                            
                            # Assign the next activity a resource and let it run
                            trace.StartNextActivity(self.P_SimulationMode, simulatedTimestep, traceSched['Resource'])
                            
                            # Remove trace from current schedule
                            del schedule[trace.case]
                            del availableResources[traceSched['Resource']]
                            
                            # Again try to determine whether we can skip unimportant timesteps for the simulation
                            remainingTime = trace.GetRemainingActivityTime(self.TimestampMode, simulatedTimestep)
                            if remainingTime < minRemainingTime:
                                minRemainingTime = remainingTime
                                
                        # else:
                        #     print("    -> Warning: Resource scheduled but currently unavailable!")

            if minRemainingTime > 0:
                print(f"{simulatedTimestep} - {minRemainingTime}")
                simulatedTimestep += minRemainingTime
            else:
                simulatedTimestep += 1
            #self.printProgressBar(len(self.completedTraces), self.traceCount, prefix='Progress:', suffix='Complete', length=50)
        print(f"Total time for simulation {time.time() - simStart :.1f}s") 
        print(f"    -> Windows simulated {currentWindow} (given: {len(self.P_Windows)} / additional: {currentWindow - len(self.P_Windows)})")
                
    
    def ExportSimulationLog(self, logPath):
        log = []
        
        # Determine which timestamps to use
        ts = 1 # By default TimestampModes.END
        if self.TimestampMode == TimestampModes.BOTH:
            ts = None
        elif self.TimestampMode == TimestampModes.START:
            ts = 0
            
        colCase = []
        colAct = []
        colRes = []
        colTS = []
            
        for trace in self.completedTraces:
            if ts is not None:
                for x in trace.history:
                    colCase.append(trace.case)
                    colAct.append(x[3][0])
                    colRes.append(x[2])
                    colTS.append(datetime.fromtimestamp(x[ts], timezone.utc))
                    # History entry : (start_ts, end_ts, res, (a,r,ts)
            else:
                log.append([{'concept:name': x[3][0],
                'org:resource': x[2],
                self.TimestampAttribute[0]: x[0],
                self.TimestampAttribute[1]: x[1]} for x in trace.history]) #History entry : (start_ts, end_ts, res, (a,r,ts)
        
        
        df = pd.DataFrame(list(zip(colCase, colAct, colTS, colRes)),
                         columns=['case', 'concept:name', 'time:timestamp', 'org:resource'])
        parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case'}
        el = log_converter.apply(df, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)

        xes_exporter.apply(el, logPath)
        del log
        del df
        del el