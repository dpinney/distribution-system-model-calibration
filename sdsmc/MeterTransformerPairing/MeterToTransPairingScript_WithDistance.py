# -*- coding: utf-8 -*-
"""
BSD 3-Clause License

Copyright 2021 National Technology & Engineering Solutions of Sandia, LLC (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights in this software.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""


##############################################################################

# Import standard Python libraries
import sys
import numpy as np
#import datetime
#from copy import deepcopy
from pathlib import Path
import pandas as pd

# Import custom libraries
if __package__ is None or __package__ == '':
    import M2TUtils
    import M2TFuncs
else:
    from . import M2TUtils
    from . import M2TFuncs
 
###############################################################################


###############################################################################
# Input Data Notes

# custIDInput: list of str (customers) - the list of customer IDs as strings
# transLabelsTrue: numpy array of int (1,customers) - the transformer labels for each customer as integers.  This is the ground truth transformer labels
# transLabelsErrors: numpy array of int (1,customers) - the transformer labels for each customer which may contain errors.
    # In the sample data, customer_3 transformer was changed from 1 to 2 and customer_53 transformer was changed from 23 to 22
# voltageInput: numpy array of float (measurements,customers) - the raw voltage AMI measurements for each customer in Volts
# pDataInput: numpy array of float (measurements, customers) - the real power measurements for each customer in Watts
# latInput: list of float (customers) - the latitude (or x-coordinate) for each customer
# lonInput: list of float (customers) - the longitude (or y-coordinate) for each customer

# Note that the indexing of all variables above should match in the customer index, i.e. custIDInput[0], transLabelsInput[0,0], voltageInput[:,0], pDataInput[:,0], and qDataInput[:,0] should all be the same customer

###############################################################################

if __name__ == '__main__':
    useTrueLabels = True # This flag specifies when the ground truth labels are available for use or not
    # This should be true for testing using the provided sample dataset

    # Load Sample data
    currentDirectory = Path.cwd()
    filePath = Path(currentDirectory.parent,'SampleData')
    filename = Path(filePath,'VoltageData_AMI.npy')
    voltageInput = np.load(filename)
    filename = Path(filePath,'RealPowerData_AMI.npy')
    pDataInput = np.load(filename)
    filename = Path(filePath,'ReactivePowerData_AMI.npy')
    qDataInput = np.load(filename)
    filename = Path(filePath,'TransformerLabelsErrors_AMI.npy')
    transLabelsErrors = np.load(filename)
    filename = Path(filePath,'CustomerIDs_AMI.npy')
    custIDInput = list(np.load(filename))
    filename = Path(filePath,'CustomerLat.npy')
    latInput = list(np.load(filename))
    filename = Path(filePath,'CustomerLon.npy')
    lonInput = list(np.load(filename))

    if useTrueLabels:
        filename = Path(filePath,'TransformerLabelsTrue_AMI.npy')
        transLabelsTrue = np.load(filename)
        
    saveResultsPath = Path(currentDirectory,'Results_M2T_PVLabelsDist')
    ###############################################################################

    ###############################################################################
    # Data pre-processing
    # Convert the raw voltage measurements into per unit and difference (delta voltage) representation
    vPU = M2TUtils.ConvertToPerUnit_Voltage(voltageInput)
    vDV = M2TUtils.CalcDeltaVoltage(vPU)

    # Create lat/lon dictionary
    custLatLon = {}
    for custCtr in range(0,len(custIDInput)):
        custLatLon[custIDInput[custCtr]] = [latInput[custCtr],lonInput[custCtr]]
        
    # Calulate pairwise distance matrix using the customer coordinates
    distMatrix = M2TUtils.CreateDistanceMatrix(custLatLon, custIDInput, distTypeFlag='euclidean')


    ##############################################################################
    #
    #        Error Flagging Section - Correlation Coefficient Analysis

    # Calculate CC Matrix
    ccMatrix,noVotesIndex,noVotesIDs = M2TUtils.CC_EnsMedian(vDV,windowSize=384,custID=custIDInput)
    # The function CC_EnsMedian takes the median CC across windows in the dataset. 
    # This is mainly done to deal with the issue of missing measurements in the dataset
    # If your data does not have missing measurements you could use numpy.corrcoef directly

    # Do a sweep of possible CC Thresholds and rank the flagged results
    notMemberVector = [0.25,0.26,0.27,0.28,0.29,0.30,0.31,0.32,0.33,0.34,0.35,0.36,0.37,0.38,0.39,0.4,0.41,0.42,0.43,0.44,0.45,0.46,0.47,0.48,0.49,0.50,0.51,0.52,0.53,0.54,0.55,0.56,0.57,0.58,0.59,0.60,0.61,0.62,0.63,0.64,0.65,0.66,0.67,0.68,0.69,0.70,0.71,0.72,0.73,0.74,0.75,0.76,0.78,0.79,0.80,0.81,0.82,0.83,0.84,0.85,0.86,0.87,0.88,0.90,0.91]
    allFlaggedTrans, allNumFlagged, rankedFlaggedTrans, rankedTransThresholds = M2TFuncs.RankFlaggingBySweepingThreshold(transLabelsErrors,notMemberVector,ccMatrix)
    # Plot the number of flagged transformers for all threshold values
    M2TUtils.PlotNumFlaggedTrans_ThresholdSweep(notMemberVector,allNumFlagged,transLabelsErrors,savePath=saveResultsPath)

    # The main output from this Error Flagging section is rankedFlaggedTrans which
    # contains the list of flagged transformers ranked by correlation coefficient.
    # Transformers at the beginning of the list were flagged with lower CC, indicating
    # higher confidence that those transformers do indeed have errors.


    ##############################################################################
    #
    #             Transformer Assignment Section - Linear Regression Steps
    #

    print('Starting regression calculation')
    r2Affinity,regRDist,regRDistIndiv,mseMatrix = M2TUtils.ParamEst_LinearRegression_NoQ(voltageInput,pDataInput,savePath=saveResultsPath)

    # Grab a particular set of ranked results
    notMemberThreshold=0.7
    flaggingIndex = np.where(np.array(notMemberVector)==notMemberThreshold)[0][0]
    flaggedTrans = allFlaggedTrans[flaggingIndex]

    distThresh = 300  # This is an important parameter - it specifies the allowed distance away that a customer may be re-assigned to a new transformer.  
    # 300 meaning that only transformer groupings within distance 300 will be considered as possible new transformer groupings for a customer being re-assigned
    predictedTransLabels, predictedTransStrLabels = M2TFuncs.CorrectFlaggedTransformers_WithDist(mseMatrix, 
                                                                                                    ccMatrix,
                                                                                                    notMemberThreshold,
                                                                                                    flaggedTrans,
                                                                                                    custIDInput,
                                                                                                    transLabelsErrors,
                                                                                                    useDistFlag=True,
                                                                                                    distMatrix=distMatrix,
                                                                                                    distThreshold = distThresh,
                                                                                                    saveFlag=True)

    print('')
    print('')
    print('Meter to Transformer Pairing Algorithm Results')
    M2TUtils.PrettyPrintChangedCustomers(predictedTransLabels,transLabelsErrors,custIDInput)

    # Calculate Error Metrics
    if useTrueLabels:
        incorrectTrans,incorrectPairedIndices, incorrectPairedIDs= M2TUtils.CalcTransPredErrors(predictedTransLabels,transLabelsTrue,custIDInput,singleCustMarker=-999)
        incorrectTransOrg,incorrectPairedIndicesOrg, incorrectPairedIDsOrg= M2TUtils.CalcTransPredErrors(transLabelsErrors,transLabelsTrue,custIDInput, singleCustMarker=-999)
        improvementNum = (len(incorrectTransOrg) - len(incorrectTrans))
        improvementPercent = np.round(((improvementNum  / len(incorrectTransOrg)) * 100),decimals=2)
        print('')
        print('There were originally ' + str(len(incorrectTransOrg)) + ' incorrect transformer groupings with the injected incorrect labels')
        print('After running algorithm there are ' + str(len(incorrectTrans)) + ' incorrect transformer groupings')
        print(str(improvementNum) + ' transformer groupings were corrected, which is an improvement of ' + str(improvementPercent) + '%')

    # Write outputs to csv file
    print('')
    filename = 'outputsAll_M2T_NoQ.csv'
    if useTrueLabels:
        df = pd.DataFrame()
        df['customer ID'] = custIDInput
        df['Original Transformer Labels (with errors)'] = transLabelsErrors[0,:]
        df['Predicted Transformer Labels'] = predictedTransLabels[0,:]
        df['Actual Transformer Labels'] = transLabelsTrue[0,:]
        df.to_csv(Path(saveResultsPath,filename))
        print('Predicted Transformer labels written to outputsAll_M2T_NoQ.csv')
    else:
        df = pd.DataFrame()
        df['customer ID'] = custIDInput
        df['Original Transformer Labels (with errors)'] = transLabelsErrors[0,:]
        df['Predicted Transformer Labels'] = predictedTransLabels[0,:]
        df.to_csv(Path(saveResultsPath,filename))
        print('Predicted Transformer labels written to outputsAll_M2T_NoQ.csv')


    df = pd.DataFrame()
    df['Ranked Flagged Transformers'] = flaggedTrans
    df.to_csv(Path(saveResultsPath,'outputs_RankedFlaggedTransformers.csv'))
    print('Flagged and ranked transformers written to outputs_RankedFlaggedTransformers.csv')


    changedIndices = np.where(predictedTransLabels != transLabelsErrors)[1]
    df = pd.DataFrame()
    df['customer ID'] = list(np.array(custIDInput)[changedIndices])
    df['Original Transformer Labels (with Errors)'] = transLabelsErrors[0,changedIndices]
    df['Predicted Transformer Labels'] = predictedTransLabels[0,changedIndices]
    filename = 'ChangedCustomers_M2T_NoQ.csv'
    df.to_csv(Path(saveResultsPath,filename))
    print('All customers with changed transformer labels written to ChangedCustomers_M2T_NoQ.csv')