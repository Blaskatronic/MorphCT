import sys
import signal
import traceback
import os
import numpy as np
import helperFunctions
import time as T
import random as R
from scipy.sparse import lil_matrix
import subprocess as sp
import pickle


elementaryCharge = 1.60217657E-19 # C
kB = 1.3806488E-23 # m^{2} kg s^{-2} K^{-1}
hbar = 1.05457173E-34 # m^{2} kg s^{-1}


class carrier:
    def __init__(self, chromophoreList, parameterDict, chromoID, lifetime, carrierNo, AAMorphologyDict, molIDDict):
        self.ID = carrierNo
        self.image = [0, 0, 0]
        self.initialChromophore = chromophoreList[chromoID]
        self.currentChromophore = chromophoreList[chromoID]
        if parameterDict['hopLimit'] == 0:
            self.hopLimit = None
        else:
            self.hopLimit = parameterDict['hopLimit']
        self.T = parameterDict['systemTemperature']
        self.lifetime = lifetime
        self.currentTime = 0.0
        self.holeHistoryMatrix = None
        self.electronHistoryMatrix = None
        if self.currentChromophore.species == 'Donor':
            self.carrierType = 'Hole'
            self.lambdaij = parameterDict['reorganisationEnergyDonor']
            if parameterDict['recordCarrierHistory'] is True:
                self.holeHistoryMatrix = lil_matrix((len(chromophoreList), len(chromophoreList)), dtype = int)
        elif self.currentChromophore.species == 'Acceptor':
            self.carrierType = 'Electron'
            self.lambdaij = parameterDict['reorganisationEnergyAcceptor']
            if parameterDict['recordCarrierHistory'] is True:
                self.electronHistoryMatrix = lil_matrix((len(chromophoreList), len(chromophoreList)), dtype = int)
        self.noHops = 0
        self.simDims = [[-AAMorphologyDict['lx'] / 2.0, AAMorphologyDict['lx'] / 2.0], [-AAMorphologyDict['ly'] / 2.0, AAMorphologyDict['ly'] / 2.0], [-AAMorphologyDict['lz'] / 2.0, AAMorphologyDict['lz'] / 2.0]]
        self.displacement = None
        self.molIDDict = molIDDict

    def calculateHopRate(self, lambdaij, Tij, deltaEij):
        # Semiclassical Marcus Hopping Rate Equation
        kij = ((2 * np.pi) / hbar) * (Tij ** 2) * np.sqrt(1.0 / (4 * lambdaij * np.pi * kB * self.T)) * np.exp(-((deltaEij + lambdaij)**2) / (4 * lambdaij * kB * self.T))
        return kij

    def determineHopTime(self, rate):
        # Use the KMC algorithm to determine the wait time to this hop
        if rate != 0:
            while True:
                x = R.random()
                # Ensure that we don't get exactly 0.0 or 1.0, which would break our logarithm
                if (x != 0.0) and (x != 1.0):
                    break
            tau = - np.log(x) / rate
        else:
            # If rate == 0, then make the hopping time extremely long
            tau = 1E99
        return tau

    def calculateHop(self, chromophoreList):
        # Terminate if the next hop would be more than the termination limit
        if self.hopLimit is not None:
            if self.noHops + 1 > self.hopLimit:
                return 1
        if parameterDict['useAverageHopRates'] is True:
            # Use the average hop values given in the parameter dict to pick a hop
            for neighbourDetails in self.currentChromophore.neighbours:
                neighbour = chromophoreList[neighbourDetails[0]]
                assert(neighbour.ID == neighbourDetails[0])
                if self.molIDDict[self.currentChromophore.ID] == self.molIDDict[neighbour.ID]:
                    hopRate = parameterDict['averageIntraHopRate']
                else:
                    hopRate = parameterDict['averageInterHopRate']
                hopTime = self.determineHopTime(hopRate)
                # Keep track of the chromophoreID and the corresponding tau
                hopTimes.append([neighbour.ID, hopTime])
        else:
            # Determine the hop times to all possible neighbours
            hopTimes = []
            # Obtain the reorganisation energy in J (from eV in the parameter file)
            for neighbourIndex, transferIntegral in enumerate(self.currentChromophore.neighboursTI):
                # Ignore any hops with a NoneType transfer integral (usually due to an ORCA error)
                if transferIntegral is None:
                    continue
                deltaEij = self.currentChromophore.neighboursDeltaE[neighbourIndex]
                # All of the energies are in eV currently, so convert them to J
                hopRate = self.calculateHopRate(self.lambdaij * elementaryCharge, transferIntegral * elementaryCharge, deltaEij * elementaryCharge)
                hopTime = self.determineHopTime(hopRate)
                # Keep track of the chromophoreID and the corresponding tau
                hopTimes.append([self.currentChromophore.neighbours[neighbourIndex][0], hopTime])
        # Sort by ascending hop time
        hopTimes.sort(key = lambda x:x[1])
        # Take the quickest hop
        if len(hopTimes) > 0:
            destinationChromophore = chromophoreList[hopTimes[0][0]]
        else:
            # We are trapped here, so create a dummy hop with time 1E99
            hopTimes = [[self.currentChromophore.ID, 1E99]]
        # As long as we're not limiting by the number of hops:
        if self.hopLimit is None:
            # Ensure that the next hop does not put the carrier over its lifetime
            if (self.currentTime + hopTimes[0][1]) > self.lifetime:
                # Send the termination signal to singleCoreRunKMC.py
                return 1
        # Move the carrier and send the contiuation signal to singleCoreRunKMC.py
        self.performHop(destinationChromophore, hopTimes[0][1])
        return 0

    def performHop(self, destinationChromophore, hopTime):
        initialID = self.currentChromophore.ID
        destinationID = destinationChromophore.ID
        initialPosition = self.currentChromophore.posn
        destinationPosition = destinationChromophore.posn
        deltaPosition = destinationPosition - initialPosition
        for axis in range(3):
            halfBoxLength = (self.simDims[axis][1] - self.simDims[axis][0]) / 2.0
            while deltaPosition[axis] > halfBoxLength:
                # Crossed over a negative boundary, decrement image by 1
                deltaPosition[axis] -= halfBoxLength * 2.0
                self.image[axis] -= 1
            while deltaPosition[axis] < - halfBoxLength:
                # Crossed over a positive boundary, increment image by 1
                deltaPosition[axis] += halfBoxLength * 2.0
                self.image[axis] += 1
        # Carrier image now sorted, so update its current position
        self.currentChromophore = destinationChromophore
        # Increment the simulation time
        self.currentTime += hopTime
        # Increment the hop counter
        self.noHops += 1
        # Now update the sparse history matrix
        if (self.carrierType == 'Hole') and (self.holeHistoryMatrix is not None):
            self.holeHistoryMatrix[initialID, destinationID] += 1
        elif (self.carrierType == 'Electron') and (self.electronHistoryMatrix is not None):
            self.electronHistoryMatrix[initialID, destinationID] += 1


class terminationSignal:
    killSent = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.catchKill)
        signal.signal(signal.SIGTERM, self.catchKill)

    def catchKill(self, signum, frame):
        self.killSent = True


class Terminate(Exception):
    '''This class is raised to terminate a KMC simulation'''
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return self.string


def savePickle(saveData, savePickleName):
    with open(savePickleName, 'wb+') as pickleFile:
        pickle.dump(saveData, pickleFile)
    helperFunctions.writeToFile(logFile, ['Pickle file saved successfully as ' + savePickleName + '!'])


def calculateDisplacement(initialPosition, finalPosition, finalImage, simDims):
    displacement = [0.0, 0.0, 0.0]
    for axis in range(3):
        displacement[axis] = (finalPosition[axis] - initialPosition[axis]) + (finalImage[axis] * (simDims[axis][1] - simDims[axis][0]))
    return np.linalg.norm(np.array(displacement))


def initialiseSaveData(nChromos, seed):
    return {'seed': seed, 'ID': [], 'image': [], 'lifetime': [], 'currentTime': [], 'noHops': [], 'displacement': [], 'holeHistoryMatrix': lil_matrix((nChromos, nChromos), dtype = int), 'electronHistoryMatrix': lil_matrix((nChromos, nChromos), dtype = int), 'initialPosition': [], 'finalPosition': [], 'carrierType':[]}


def splitMolecules(inputDictionary):
    # Split the full morphology into individual molecules
    moleculeAAIDs = []
    moleculeLengths = []
    # Create a lookup table `neighbour list' for all connected atoms called {bondedAtoms}
    bondedAtoms = helperFunctions.obtainBondedList(inputDictionary['bond'])
    moleculeList = [i for i in range(len(inputDictionary['type']))]
    # Recursively add all atoms in the neighbour list to this molecule
    for molID in range(len(moleculeList)):
        moleculeList = updateMolecule(molID, moleculeList, bondedAtoms)
    # Here we have a list of len(atoms) where each index gives the molID
    molIDDict = {}
    for chromo in chromophoreList:
        AAIDToCheck = chromo.AAIDs[0]
        molIDDict[chromo.ID] = moleculeList[AAIDToCheck]
    return molIDDict


def updateMolecule(atomID, moleculeList, bondedAtoms):
    # Recursively add all neighbours of atom number atomID to this molecule
    try:
        for bondedAtom in bondedAtoms[atomID]:
            # If the moleculeID of the bonded atom is larger than that of the current one,
            # update the bonded atom's ID to the current one's to put it in this molecule,
            # then iterate through all of the bonded atom's neighbours
            if moleculeList[bondedAtom] > moleculeList[atomID]:
                moleculeList[bondedAtom] = moleculeList[atomID]
                moleculeList = updateMolecule(bondedAtom, moleculeList, bondedAtoms)
            # If the moleculeID of the current atom is larger than that of the bonded one,
            # update the current atom's ID to the bonded one's to put it in this molecule,
            # then iterate through all of the current atom's neighbours
            elif moleculeList[bondedAtom] < moleculeList[atomID]:
                moleculeList[atomID] = moleculeList[bondedAtom]
                moleculeList = updateMolecule(atomID, moleculeList, bondedAtoms)
            # Else: both the current and the bonded atom are already known to be in this
            # molecule, so we don't have to do anything else.
    except KeyError:
        # This means that there are no bonded CG sites (i.e. it's a single molecule)
        pass
    return moleculeList


if __name__ == '__main__':
    KMCDirectory = sys.argv[1]
    CPURank = int(sys.argv[2])
    overwrite = False
    try:
        overwrite = bool(sys.argv[3])
    except:
        pass
    # Load `jobsToRun' which is a list, where each element contains the [carrier.ID, carrier.lifetime, carrier.carrierType]
    pickleFileName = KMCDirectory + '/KMCData_%02d.pickle' % (CPURank)
    with open(pickleFileName, 'rb') as pickleFile:
        jobsToRun = pickle.load(pickleFile)
    logFile = KMCDirectory + '/KMClog_' + str(CPURank) + '.log'
    # Reset the log file
    with open(logFile, 'wb+') as logFileHandle:
        pass
    helperFunctions.writeToFile(logFile, ['Found ' + str(len(jobsToRun)) + ' jobs to run.'])
    # Set the affinities for this current process to make sure it's maximising available CPU usage
    currentPID = os.getpid()
    #try:
    #    affinityJob = sp.Popen(['taskset', '-pc', str(CPURank), str(currentPID)], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE).communicate()
    #    # helperFunctions.writeToFile(logFile, affinityJob[0].split('\n')) #stdOut for affinity set
    #    # helperFunctions.writeToFile(logFile, affinityJob[1].split('\n')) #stdErr for affinity set
    #except OSError:
    #    helperFunctions.writeToFile(logFile, ["Taskset command not found, skipping setting of processor affinity..."])
    # Now load the main morphology pickle (used as a workaround to obtain the chromophoreList without having to save it in each carrier [very memory inefficient!])
    pickleDir = KMCDirectory.replace('/KMC', '/code')
    for fileName in os.listdir(pickleDir):
        if 'pickle' in fileName:
            mainMorphologyPickleName = pickleDir + '/' + fileName
    helperFunctions.writeToFile(logFile, ['Found main morphology pickle file at ' + mainMorphologyPickleName + '! Loading data...'])
    AAMorphologyDict, CGMorphologyDict, CGToAAIDMaster, parameterDict, chromophoreList = helperFunctions.loadPickle(mainMorphologyPickleName)
    helperFunctions.writeToFile(logFile, ['Main morphology pickle loaded!'])
    if parameterDict['useAverageHopRates'] is True:
        # Chosen to split hopping by inter-intra molecular hops, so get molecule data
        molIDDict = splitMolecules(AAMorphologyDict)
        # molIDDict is a dictionary where the keys are the chromoIDs, and the vals are the molIDs
    else:
        molIDDict = None
    # Attempt to catch a kill signal to ensure that we save the pickle before termination
    killer = terminationSignal()
    seed = R.randint(0, sys.maxsize)
    R.seed(seed)
    # Save the pickle as a list of `saveCarrier' instances that contain the bare minimum
    saveData = initialiseSaveData(len(chromophoreList), seed)
    if parameterDict['recordCarrierHistory'] is False:
        saveData['holeHistoryMatrix'] = None
        saveData['electronHistoryMatrix'] = None
    t0 = T.time()
    saveTime = T.time()
    saveSlot = 'slot1'
    try:
        for jobNumber, [carrierNo, lifetime, carrierType] in enumerate(jobsToRun):
            t1 = T.time()
            # Find a random position to start the carrier in
            while True:
                startChromoID = R.randint(0, len(chromophoreList) - 1)
                if (carrierType == 'Electron') and (chromophoreList[startChromoID].species != 'Acceptor'):
                    continue
                elif (carrierType == 'Hole') and (chromophoreList[startChromoID].species != 'Donor'):
                    continue
                break
            # Create the carrier instance
            thisCarrier = carrier(chromophoreList, parameterDict, startChromoID, lifetime, carrierNo, AAMorphologyDict, molIDDict)
            terminateSimulation = False
            while terminateSimulation is False:
                terminateSimulation = bool(thisCarrier.calculateHop(chromophoreList))
                if killer.killSent is True:
                    raise Terminate('Kill command sent, terminating KMC simulation...')
            # Now the carrier has finished hopping, let's calculate its vitals
            initialPosition = thisCarrier.initialChromophore.posn
            finalPosition = thisCarrier.currentChromophore.posn
            finalImage = thisCarrier.image
            simDims = thisCarrier.simDims
            thisCarrier.displacement = calculateDisplacement(initialPosition, finalPosition, finalImage, simDims)
            # Now the calculations are completed, create a barebones class containing the save data
            importantData = ['ID', 'image', 'lifetime', 'currentTime', 'noHops', 'displacement', 'carrierType']
            for name in importantData:
                saveData[name].append(thisCarrier.__dict__[name])
            # Update the carrierHistoryMatrix
            if parameterDict['recordCarrierHistory'] is True:
                if thisCarrier.carrierType == 'Hole':
                    saveData['holeHistoryMatrix'] += thisCarrier.holeHistoryMatrix
                elif thisCarrier.carrierType == 'Electron':
                    saveData['electronHistoryMatrix'] += thisCarrier.electronHistoryMatrix
            # Then add in the initial and final positions
            saveData['initialPosition'].append(initialPosition)
            saveData['finalPosition'].append(finalPosition)
            t2 = T.time()
            elapsedTime = float(t2) - float(t1)
            if elapsedTime < 60:
                timeunits = 'seconds.'
            elif elapsedTime < 3600:
                elapsedTime /= 60.0
                timeunits = 'minutes.'
            elif elapsedTime < 86400:
                elapsedTime /= 3600.0
                timeunits = 'hours.'
            else:
                elapsedTime /= 86400.0
                timeunits = 'days.'
            elapsedTime = '%.1f' % (float(elapsedTime))
            helperFunctions.writeToFile(logFile, ['Carrier hopped ' + str(thisCarrier.noHops) + ' times, over ' + str(thisCarrier.currentTime) + ' seconds, into image ' + str(thisCarrier.image) + ', for a displacement of ' + str(thisCarrier.displacement) + ', in ' + str(elapsedTime) + ' wall-clock ' + str(timeunits)])
            # Save the pickle file every hour
            if (t2 - saveTime) > 3600:
                print("Completed", jobNumber, "of", len(jobsToRun), "jobs. Making checkpoint at %3d%%" % (np.round((jobNumber + 1) / float(len(jobsToRun)) * 100)))
                helperFunctions.writeToFile(logFile, ['Completed ' + str(jobNumber) + ' jobs. Making checkpoint at %3d%%' % (np.round(jobNumber / float(len(jobsToRun)) * 100))])
                savePickle(saveData, pickleFileName.replace('Data', saveSlot + 'Results'))
                if saveSlot == 'slot1':
                    saveSlot = 'slot2'
                elif saveSlot == 'slot2':
                    saveSlot = 'slot1'
                saveTime = T.time()
    except Exception as errorMessage:
        print(traceback.format_exc())
        print("Saving the pickle file cleanly before termination...")
        helperFunctions.writeToFile(logFile, [str(errorMessage)])
        helperFunctions.writeToFile(logFile, ['Saving the pickle file cleanly before termination...'])
        savePickle(saveData, pickleFileName.replace('Data', 'TerminatedResults'))
        print("Pickle saved! Exitting Python...")
        exit()
    t3 = T.time()
    elapsedTime = float(t3) - float(t0)
    if elapsedTime < 60:
        timeunits = 'seconds.'
    elif elapsedTime < 3600:
        elapsedTime /= 60.0
        timeunits = 'minutes.'
    elif elapsedTime < 86400:
        elapsedTime /= 3600.0
        timeunits = 'hours.'
    else:
        elapsedTime /= 86400.0
        timeunits = 'days.'
    elapsedTime = '%.1f' % (float(elapsedTime))
    helperFunctions.writeToFile(logFile, ['All jobs completed in ' + elapsedTime + ' ' + timeunits])
    helperFunctions.writeToFile(logFile, ['Saving the pickle file cleanly before termination...'])
    savePickle(saveData, pickleFileName.replace('Data', 'Results'))
    helperFunctions.writeToFile(logFile, ['Exiting normally...'])
