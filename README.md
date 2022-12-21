# PM_FairScheduling

### Requirements & Installation:

- This code is written in Python 3.9.13. In addition, you need to install the packages listed in requirements.txt.
- To install:
  ```
  $ pip install -r requirements.txt
  ```
- If you want to use the prediction functionality, you will need to set up Nvidia CUDA and CUDNN according to your machine and the installed tensorflow-gpu version (2.10.1 for requirements.txt install).
  CUDA v11.8 is compatible to this tensorflow version.


### Quickstart-Usage
 ```
  $ python main.py -l logs/log_ResReduced.xes -o logs/output.xes -F W --FairnessBacklogN 500
  ```
  - Useable Script Parameters:
     - -h, --help            show this help message and exit
     - -l LOG, --log LOG     The path to the event-log to be loaded
     - -o OUT, --out OUT     The path to which the simulated event-log will be exported
     - -F <TYPE>  W: Amount of work / T: Time spent working
     - --FairnessBacklogN <NUMBER> Number of passed windows to consider for fairness calculations
     - -v, --verbose         Display additional runtime information

### Multi-Experiment Setup
The simulator is built to allow multiple experiments running in parallel.
An example for a multi-experiment configuration can be found in 'multisim.cfg', where you can specify the arguments of the experiment in the exact same way you would provide them to the commandline when calling main.py
Just pass the config file as an argument to the main.py and optionally specify the amount of experiments/cores running in parallel:
 ```
  $ python main.py -M multisim.cfg --MultiSimCores 10
  ```

### Event-Prediction
To start an instance of the standalone predictor service, you need to specify which model(s) are to be loaded, on which port the service will be listening for connections and that it is indeed a standalone:
 ```
  $ python main.py --PredictorModel 'models/modelA.h5' 'models/modelB.h5' --PredictorPort 5050 --PredictorStandalone
 ```

To connect to a predictor service for the simulation, specify the host and port the service is running on and which model to use for predictions, then continue with the regular simulation parameters:
 ```
  $ python main.py --PredictorModel 'modelA' --PredictorPort 5050 --PredictorHost 'cluster7.contoso.com' (-l .... or -e ....)
  ```
