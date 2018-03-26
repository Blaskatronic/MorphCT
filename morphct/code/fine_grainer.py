import copy
import numpy as np
from morphct.code import helper_functions as hf
import sys


class morphology:
    def __init__(self, morphologyXML, morphologyName, parameterDict, chromophoreList):
        # Need to save the parameterDict in full as well as its component values because we're going to update the parameterDict with the new type mappings by the end of this code module.
        self.parameterDict = parameterDict
        # Import parameters from the parXX.py
        for key, value in parameterDict.items():
            self.__dict__[key] = value
        self.xmlPath = morphologyXML
        self.morphologyName = morphologyName
        # self.inputSigma is the `compression value' in Angstroms that has been used to scale the morphology
        # E.G. the P3HT template uses sigma = 1, but the Marsh morphologies use sigma = 3.
        self.CGDictionary = helperFunctions.loadMorphologyXML(self.xmlPath, sigma=self.inputSigma)
        self.CGDictionary = helperFunctions.addUnwrappedPositions(self.CGDictionary)
        self.chromophoreList = chromophoreList

    def analyseMorphology(self):
        # Split the morphology into individual molecules
        print("Finding molecules...")
        moleculeIDs, moleculeLengths = self.splitMolecules()
        rollingAAIndex = 0
        CGMorphologyDict = {}
        AAMorphologyDict = {}
        # Set the AAMorphology and CGMorphology system sizes to the same as the input file system size
        for boxDimension in ['lx', 'ly', 'lz', 'xy', 'xz', 'yz']:
            CGMorphologyDict[boxDimension] = self.CGDictionary[boxDimension]
            AAMorphologyDict[boxDimension] = self.CGDictionary[boxDimension]
        CGToAAIDMaster = []  # This is a list of dictionaries. Elements in the list correspond to molecules
        # (useful for splitting out individual molecules for the xyz conversion) within the element, the
        # dictionary key is the CG site, the value is a list containing the CG type (e.g. 'thio') as the
        # first element and then another list of all the AAIDs corresponding to that CG site as the second
        # element.

        # If no CGToTemplate info is present in the parameter dict, then we can assume that the morphology 
        # is already fine-grained and so we can just return the important information and skip this module
        if len(self.CGToTemplateDirs) == 0:
            print("No CG to AA data found in parameter file - the morphology is already fine-grained! Skipping this module...")
            # Write the XML file and create the pickle
            print("Writing XML file...")
            AAFileName = self.outputMorphDir + '/' + self.morphologyName + '/morphology/' + self.morphologyName + '.xml'
            atomisticMorphology = helperFunctions.addUnwrappedPositions(self.CGDictionary)
            # Now write the morphology XML
            helperFunctions.writeMorphologyXML(atomisticMorphology, AAFileName)
            # And finally write the pickle with the CGDictionary as None (to indicate to MorphCT that no
            # fine-graining has taken place), but the other parameters assigned as required.
            pickleLocation = self.outputMorphDir + '/' + self.morphologyName + '/code/' + self.morphologyName + '.pickle'
            helperFunctions.writePickle((atomisticMorphology, None, None, self.parameterDict, self.chromophoreList), pickleLocation)
            return atomisticMorphology, None, None, self.parameterDict, self.chromophoreList

        # Create a ghost particle dictionary to be added at the end of the morphology.
        # This way, we don't mess up the order of atoms later on when trying to split
        # back up into individual molecules and monomers.
        # The ghost dictionary contains all of the type T and type X particles that will
        # anchor the thiophene rings to the CG COM positions.
        ghostDictionary = {'position': [], 'image': [], 'unwrapped_position': [], 'mass': [], 'diameter': [], 'type': [], 'body': [], 'bond': [], 'angle': [], 'dihedral': [], 'improper': [], 'charge': []}

        # Need to check for atom-type conflicts and suitably increment the type indices if more than
        # one molecule type is being fine-grained
        newTypeMappings = self.getNewTypeMappings(self.CGToTemplateDirs, self.CGToTemplateForceFields)
        # Need to update the self.parameterDict, which will be rewritten at the end of this module
        self.parameterDict['newTypeMappings'] = newTypeMappings
        molecule = []
        uniqueMappings = []
        CGSites, mappings = helperFunctions.parallelSort(list(newTypeMappings.keys()), list(newTypeMappings.values()))
        for index, mapping in enumerate(mappings):
            if mapping not in uniqueMappings:
                molecule.append([])
                uniqueMappings.append(mapping)
            molecule[-1].append(CGSites[index])
        printExplanation = True
        for index, CGSites in enumerate(molecule):
            printMol = True
            initialAtoms, finalAtoms = helperFunctions.parallelSort(list(uniqueMappings[index].keys()), list(uniqueMappings[index].values()))
            for index, initialAtom in enumerate(initialAtoms):
                if initialAtom == finalAtoms[index]:
                    continue
                if printExplanation is True:
                    print("The following atom types have been remapped due to conflicting typenames in the atomistic templates:")
                    printExplanation = False
                if printMol is True:
                    print("Atom types belonging the molecule described by", repr(CGSites)+":")
                    printMol = False
                print(initialAtom, "--->", finalAtoms[index])
        print("Adding", len(moleculeIDs), "molecules to the system...")
        for moleculeNumber in range(len(moleculeIDs)):
            print("Adding molecule number", moleculeNumber, "\r", end=' ')
            sys.stdout.flush()
            # Obtain the AA dictionary for each molecule using the fine-grainining procedure
            AAMoleculeDict, CGtoAAIDs, ghostDictionary = atomistic(moleculeNumber, moleculeIDs[moleculeNumber], self.CGDictionary, moleculeLengths, rollingAAIndex, ghostDictionary, self.parameterDict).returnData()
            CGToAAIDMaster.append(CGtoAAIDs)
            # Update the morphology dictionaries with this new molecule
            for key in list(self.CGDictionary.keys()):
                if key not in ['lx', 'ly', 'lz', 'xy', 'xz', 'yz', 'time_step', 'dimensions']:
                    #if key not in CGMorphologyDict.keys():
                    #    CGMorphologyDict[key] = CGMoleculeDict[key]
                    #else:
                    #    CGMorphologyDict[key] += CGMoleculeDict[key]
                    if key not in list(AAMorphologyDict.keys()):
                        AAMorphologyDict[key] = AAMoleculeDict[key]
                    else:
                        AAMorphologyDict[key] += AAMoleculeDict[key]
            rollingAAIndex += len(AAMoleculeDict['type'])
        # Now add the ghost dictionary to the end of the morphology file
        totalNumberOfAtoms = len(AAMorphologyDict['type'])  # Should be == rollingAAIndex, but don't want to take any chances
        # Add in the wrapped positions of the ghosts. Need to know sim dims for this
        for key in ['lx', 'ly', 'lz', 'xy', 'xz', 'yz']:
            ghostDictionary[key] = AAMorphologyDict[key]
        ghostDictionary = helperFunctions.addWrappedPositions(ghostDictionary)
        for key in ['lx', 'ly', 'lz', 'xy', 'xz', 'yz']:
            ghostDictionary.pop(key)
        # The real atoms that the ghost particles are bonded to are already correct and no longer need to be changed.
        # However, the ghost particles themselves will have the wrong indices if we were to add them to the system directly.
        # Therefore, increment all of the ghost bond indices that begin with a * (ghost particle) by the total number of atoms already in the system.
        for bondNo, bond in enumerate(ghostDictionary['bond']):
            if str(bond[1])[0] == '*':
                ghostDictionary['bond'][bondNo][1] = int(bond[1][1:]) + totalNumberOfAtoms
            if str(bond[2])[0] == '*':
                ghostDictionary['bond'][bondNo][2] = int(bond[2][1:]) + totalNumberOfAtoms
        # Now append all ghosts to morphology
        for key in list(ghostDictionary.keys()):
            AAMorphologyDict[key] += ghostDictionary[key]
        # Finally, update the number of atoms
        AAMorphologyDict['natoms'] += len(ghostDictionary['type'])
        print("\n")
        # Now write the XML file and create the pickle
        print("Writing XML file...")
        AAFileName = self.outputMorphDir + '/' + self.morphologyName + '/morphology/' + self.morphologyName + '.xml'
        # Replace the `positions' with the `unwrapped_positions' ready for writing
        AAMorphologyDict = helperFunctions.replaceWrappedPositions(AAMorphologyDict)
        # Update the additionalConstraints that we put in by checking all of the constraints have the correct names before writing
        AAMorphologyDict = helperFunctions.checkConstraintNames(AAMorphologyDict)
        # Now write the morphology XML
        helperFunctions.writeMorphologyXML(AAMorphologyDict, AAFileName)
        # And finally write the pickle
        pickleLocation = self.outputMorphDir + '/' + self.morphologyName + '/code/' + self.morphologyName + '.pickle'
        helperFunctions.writePickle((AAMorphologyDict, self.CGDictionary, CGToAAIDMaster, self.parameterDict, self.chromophoreList), pickleLocation)
        return AAMorphologyDict, self.CGDictionary, CGToAAIDMaster, self.parameterDict, self.chromophoreList

    def splitMolecules(self):
        # Split the full morphology into individual molecules
        moleculeAAIDs = []
        moleculeLengths = []
        # Create a lookup table `neighbour list' for all connected atoms called {bondedAtoms}
        bondedAtoms = helperFunctions.obtainBondedList(self.CGDictionary['bond'])
        moleculeList = [i for i in range(len(self.CGDictionary['type']))]
        # Recursively add all atoms in the neighbour list to this molecule
        for molID in range(len(moleculeList)):
            moleculeList = self.updateMolecule(molID, moleculeList, bondedAtoms)
        # Create a dictionary of the molecule data
        moleculeData = {}
        for atomID in range(len(self.CGDictionary['type'])):
            if moleculeList[atomID] not in moleculeData:
                moleculeData[moleculeList[atomID]] = [atomID]
            else:
                moleculeData[moleculeList[atomID]].append(atomID)
        # Return the list of AAIDs and the lengths of the molecules
        for moleculeID in list(moleculeData.keys()):
            moleculeAAIDs.append(sorted(moleculeData[moleculeID]))
            moleculeLengths.append(len(moleculeData[moleculeID]))
        return moleculeAAIDs, moleculeLengths

    def updateMolecule(self, atomID, moleculeList, bondedAtoms):
        # Recursively add all neighbours of atom number atomID to this molecule
        try:
            for bondedAtom in bondedAtoms[atomID]:
                # If the moleculeID of the bonded atom is larger than that of the current one,
                # update the bonded atom's ID to the current one's to put it in this molecule,
                # then iterate through all of the bonded atom's neighbours
                if moleculeList[bondedAtom] > moleculeList[atomID]:
                    moleculeList[bondedAtom] = moleculeList[atomID]
                    moleculeList = self.updateMolecule(bondedAtom, moleculeList, bondedAtoms)
                # If the moleculeID of the current atom is larger than that of the bonded one,
                # update the current atom's ID to the bonded one's to put it in this molecule,
                # then iterate through all of the current atom's neighbours
                elif moleculeList[bondedAtom] < moleculeList[atomID]:
                    moleculeList[atomID] = moleculeList[bondedAtom]
                    moleculeList = self.updateMolecule(atomID, moleculeList, bondedAtoms)
                # Else: both the current and the bonded atom are already known to be in this
                # molecule, so we don't have to do anything else.
        except KeyError:
            # This means that there are no bonded CG sites (i.e. it's a single molecule)
            pass
        return moleculeList

    def getNewTypeMappings(self, CGToTemplateDirs, CGToTemplateForceFields):
        forceFieldLocations = []
        forceFieldMappings = []
        morphologyAtomTypes = []
        CGToTemplateMappings = {}
        for CGSite, directory in CGToTemplateDirs.items():
            FFLoc = directory + '/' + CGToTemplateForceFields[CGSite]
            if FFLoc not in forceFieldLocations:
                forceFieldLocations.append(FFLoc)
        for FFLoc in forceFieldLocations:
            mappingForThisFF = {}
            forceField = helperFunctions.loadFFXML(FFLoc)
            for ljInteraction in forceField['lj']:
                atomType = ljInteraction[0]
                while atomType in morphologyAtomTypes:
                    # Atom type already exists in morphology, so increment the atomType number by one
                    for i in range(1,len(atomType)):
                        # Work out where the integer start so we can increment it (should be i = 1 for one-character element names)
                        try:
                            integer = int(atomType[i:])
                            break
                        except:
                            continue
                    atomType = atomType[:i] + str(integer + 1)
                morphologyAtomTypes.append(atomType)
                mappingForThisFF[ljInteraction[0]] = atomType
            forceFieldMappings.append(mappingForThisFF)
        for CGSite, directory in CGToTemplateDirs.items():
            FFLoc = directory + '/' + CGToTemplateForceFields[CGSite]
            CGToTemplateMappings[CGSite] = forceFieldMappings[forceFieldLocations.index(FFLoc)]
        return CGToTemplateMappings


class atomistic:
    def __init__(self, moleculeIndex, siteIDs, CGDictionary, moleculeLengths, rollingAAIndex, ghostDictionary, parameterDict):
        # This class sees individual molecules.
        self.noAtomsInMorphology = rollingAAIndex
        self.moleculeIndex = moleculeIndex
        self.moleculeLengths = moleculeLengths
        self.siteIDs = siteIDs
        self.CGDictionary = CGDictionary
        # Get the dictionary of all the CG sites in this molecule
        #self.CGMonomerDictionary = self.getCGMonomerDict()
        # Import the parXX.py parameters
        for key, value in parameterDict.items():
            self.__dict__[key] = value
        self.AATemplatesDictionary = {}
        # Load the template file for each CG atom
        for CGAtomType in list(self.CGToTemplateFiles.keys()):
            templateDictionary = helperFunctions.loadMorphologyXML(self.CGToTemplateDirs[CGAtomType] + '/' + self.CGToTemplateFiles[CGAtomType])
            templateDictionary = self.remapAtomTypes(templateDictionary, parameterDict['newTypeMappings'][CGAtomType])
            templateDictionary = helperFunctions.addUnwrappedPositions(templateDictionary)
            self.AATemplatesDictionary[CGAtomType] = templateDictionary
        self.AADictionary, self.atomIDLookupTable, self.ghostDictionary = self.runFineGrainer(ghostDictionary)

    def returnData(self):
        # Return the important fine-grained results from this class
        return self.AADictionary, self.atomIDLookupTable, self.ghostDictionary

    def getCGMonomerDict(self):
        CGMonomerDictionary = {'position': [], 'image': [], 'mass': [], 'diameter': [], 'type': [], 'body': [], 'bond': [], 'angle': [], 'dihedral': [], 'improper': [], 'charge': [], 'lx': 0, 'ly': 0, 'lz': 0, 'xy' : 0, 'xz': 0, 'yz': 0}
        # First, do just the positions and find the newsiteIDs for each CG site
        for siteID in self.siteIDs:
            CGMonomerDictionary['position'].append(self.CGDictionary['position'][siteID])
        # Now sort out the other one-per-atom properties
        for key in ['image', 'mass', 'diameter', 'type', 'body', 'charge']:
            if len(self.CGDictionary[key]) != 0:
                for siteID in self.siteIDs:
                    CGMonomerDictionary[key].append(self.CGDictionary[key][siteID])
        # Now rewrite the bonds based on the newsiteIDs
        for key in ['bond', 'angle', 'dihedral', 'improper']:
            for element in self.CGDictionary[key]:
                for siteID in self.siteIDs:
                    if (siteID in element) and (element not in CGMonomerDictionary[key]):
                        CGMonomerDictionary[key].append(element)
        # Now update the box parameters
        for key in ['lx', 'ly', 'lz']:
            CGMonomerDictionary[key] = self.CGDictionary[key]
        CGMonomerDictionary = helperFunctions.addUnwrappedPositions(CGMonomerDictionary)
        CGMonomerDictionary['natoms'] = len(CGMonomerDictionary['position'])
        return CGMonomerDictionary

    def remapAtomTypes(self, templateDict, mappings):
        # Remap the atom types first
        for index, atomType in enumerate(templateDict['type']):
            templateDict['type'][index] = mappings[atomType]
        # Then rename the constraints appropriately
        constraintTypes = ['bond', 'angle', 'dihedral', 'improper']
        for constraintType in constraintTypes:
            for constraintIndex, constraint in enumerate(templateDict[constraintType]):
                newConstraint0 = ""  # Create a new constraint label
                for atomID in constraint[1:]:
                    newConstraint0 += templateDict['type'][atomID]
                    newConstraint0 += '-'
                    # Assign the constraint label
                templateDict[constraintType][constraintIndex][0] = newConstraint0[:-1]
        return templateDict

    def runFineGrainer(self, ghostDictionary):
        AADictionary = {'position': [], 'image': [], 'unwrapped_position': [], 'mass': [], 'diameter': [], 'type': [], 'body': [], 'bond': [], 'angle': [], 'dihedral': [], 'improper': [], 'charge': [], 'lx': 0, 'ly': 0, 'lz': 0, 'xy' : 0, 'xz': 0, 'yz': 0}
        # Find the COMs of each CG site in the system, so that we know where to move the template to
        CGCoMs, self.CGToTemplateAAIDs = self.getAATemplatePosition(self.CGToTemplateAAIDs)
        # Need to keep track of the atom ID numbers globally - runFineGrainer sees individual monomers, atomistic sees molecules and the XML needs to contain the entire morphology.
        noAtomsInMolecule = 0
        CGTypeList = {}
        for siteID in self.siteIDs:
            CGTypeList[siteID] = self.CGDictionary['type'][siteID]
        # Sort the CG sites into monomers so we can iterate over each monomer in order to perform the fine-graining
        monomerList = self.sortIntoMonomers(CGTypeList)
        currentMonomerIndex = sum(self.moleculeLengths[:self.moleculeIndex])
        atomIDLookupTable = {}
        # Calculate the total number of permitted atoms
        totalPermittedAtoms = self.totalPermittedAtoms(monomerList)
        # Set the initial and final atom indices to None initially, so that we don't add terminating units for small molecules
        startAtomIndex = None
        endAtomIndex = None
        for monomerNo, monomer in enumerate(monomerList):
            # This monomer should have the same template file for all CG sites in the monomer, if not we've made a mistake in splitting the monomers. So check this:
            templateFiles = []
            monomerCGTypes = []
            for CGSite in monomer:
                templateFiles.append(self.CGToTemplateFiles[self.CGDictionary['type'][CGSite]])
                monomerCGTypes.append(self.CGDictionary['type'][CGSite])
            if len(set(templateFiles)) != 1:
                print(monomer)
                print(monomerCGTypes)
                print(templateFiles)
                raise SystemError('NOT ALL MONOMER SITES ARE THE SAME TEMPLATE')
            # Copy the template dictionary for editing for this monomer
            thisMonomerDictionary = copy.deepcopy(self.AATemplatesDictionary[self.CGDictionary['type'][monomer[0]]])
            for key in ['lx', 'ly', 'lz']: #TODO tilts
                thisMonomerDictionary[key] = self.CGDictionary[key]
            # Include the image tag in case it's not present in the template
            if len(thisMonomerDictionary['image']) == 0:
                thisMonomerDictionary['image'] = [[0, 0, 0]] * len(thisMonomerDictionary['position'])
            for siteID in monomer:
                sitePosn = np.array(self.CGDictionary['unwrapped_position'][siteID])
                siteTranslation = sitePosn - CGCoMs[CGTypeList[siteID]]
                atomIDLookupTable[siteID] = [CGTypeList[siteID], [x + noAtomsInMolecule + self.noAtomsInMorphology for x in self.CGToTemplateAAIDs[CGTypeList[siteID]]]]
                # Add the atoms in based on the CG site position
                for AAID in self.CGToTemplateAAIDs[CGTypeList[siteID]]:
                    thisMonomerDictionary['unwrapped_position'][AAID] = list(np.array(thisMonomerDictionary['unwrapped_position'][AAID]) + siteTranslation)
                # Next sort out the rigid bodies
                if CGTypeList[siteID] in self.rigidBodySites:
                    # Every rigid body needs a ghost particle that describes its CoM
                    AAIDPositions = []
                    AAIDAtomTypes = []
                    # If the key is specified with no values, assume that all the AAIDs in the template contitute the rigid body
                    if len(self.rigidBodySites[CGTypeList[siteID]]) == 0:
                        self.rigidBodySites[CGTypeList[siteID]] = list(np.arange(len(self.CGToTemplateAAIDs[CGTypeList[siteID]])))
                    for AAID in self.rigidBodySites[CGTypeList[siteID]]:
                        thisMonomerDictionary['body'][AAID] = currentMonomerIndex
                        AAIDPositions.append(thisMonomerDictionary['unwrapped_position'][AAID])
                        AAIDAtomTypes.append(thisMonomerDictionary['type'][AAID])
                    # Now create the ghost particle describing the rigid body
                    ghostCOM = helperFunctions.calcCOM(AAIDPositions, listOfAtomTypes=AAIDAtomTypes)
                    ghostDictionary['unwrapped_position'].append(ghostCOM)
                    ghostDictionary['mass'].append(1.0)
                    ghostDictionary['diameter'].append(1.0)
                    ghostDictionary['type'].append('R' + str(CGTypeList[siteID]))
                    ghostDictionary['body'].append(currentMonomerIndex)
                    ghostDictionary['charge'].append(0.0)
                    # Then create the corresponding CG anchorpoint
                    ghostDictionary['unwrapped_position'].append(ghostCOM)
                    ghostDictionary['mass'].append(1.0)
                    ghostDictionary['diameter'].append(1.0)
                    ghostDictionary['type'].append('X' + str(CGTypeList[siteID]))
                    ghostDictionary['body'].append(-1)
                    ghostDictionary['charge'].append(0.0)
                    # Now create a bond between them
                    # We want to bond together the previous two ghost particles, so this should work as it requires no knowledge of the number of ghost particles already in the system.
                    ghostDictionary['bond'].append([str(ghostDictionary['type'][-2]) + '-' + str(ghostDictionary['type'][-1]), '*' + str(len(ghostDictionary['type']) - 2), '*' + str(len(ghostDictionary['type']) - 1)])
                else:
                    # Create a ghost particle that describe the CG anchorpoint for the non-rigid body
                    ghostDictionary['unwrapped_position'].append(self.CGDictionary['unwrapped_position'][siteID])
                    ghostDictionary['mass'].append(1.0)
                    ghostDictionary['diameter'].append(1.0)
                    ghostDictionary['type'].append('X' + str(CGTypeList[siteID]))
                    ghostDictionary['body'].append(-1)
                    ghostDictionary['charge'].append(0.0)
                    # Add in bonds between the CG anchorpoints and the atom closest to the CG site
                    # Find the atom closest to the CG site
                    closestAtomID = None
                    closestAtomPosn = 1E99
                    for AAID, AAPosition in enumerate(thisMonomerDictionary['unwrapped_position']):
                        separation = helperFunctions.calculateSeparation(self.CGDictionary['unwrapped_position'][siteID], AAPosition)
                        if separation < closestAtomPosn:
                            closestAtomPosn = separation
                            closestAtomID = AAID
                    # Add in the bond:
                    # Note that, in order to distinguish between the ghostAtomIDs and the realAtomIDs, I've put an underscore in front of the closestAtomID, and a * in front of the ghostAtomID.
                    # When incrementing the atomIDs for this monomer or this molecule, the readlAtomIDs will be incremented correctly.
                    # Later, when the ghost atoms are added to the main system, the ghostAtomIDs will be incremented according to the number of atoms in the whole system (i.e. the ghosts appear at the end of the real atoms).
                    # At this time, the realAtomIDs will be left unchanged because they are already correct for the whole system.
                    ghostDictionary['bond'].append([str(ghostDictionary['type'][-1]) + '-' + str(thisMonomerDictionary['type'][closestAtomID]), '*' + str(len(ghostDictionary['type']) - 1), '_' + str(closestAtomID + noAtomsInMolecule)])
            # DEBUG: NOTE ADD THESE BACK IN IF IT DOESN'T WORK
            #thisMonomerDictionary = helperFunctions.addWrappedPositions(thisMonomerDictionary)
            #thisMonomerDictionary = helperFunctions.addMasses(thisMonomerDictionary)
            #thisMonomerDictionary = helperFunctions.addDiameters(thisMonomerDictionary)
            # Now add in the bonds between CGSites in this monomer
            for bond in self.CGDictionary['bond']:
                if (bond[1] in monomer) and (bond[2] in monomer):
                    CGBondType = bond[0]
                    thisMonomerDictionary['bond'].append(self.CGToTemplateBonds[CGBondType])
            # Now need to add in the additionalConstraints for this monomer (which include the bond, angle and dihedral for the inter-monomer connections.
            # However, we need a check to make sure that we don't add stuff for the final monomer (because those atoms +25 don't exist in this molecule!)
            for constraint in self.additionalConstraints:
                # Firstly, skip this constraint if the current monomer doesn't have the relevant atom types
                if all([atomType in set(thisMonomerDictionary['type']) for atomType in constraint[0].split('-')]) is False:
                    continue
                # Also check that we're not at the final monomer
                atFinalMonomer = False
                for atomID in constraint[2:]:
                    if (noAtomsInMolecule + atomID + 1) > totalPermittedAtoms:
                        atFinalMonomer = True
                        break
                if atFinalMonomer is True:
                    break
                # Work out which key to write the constraint to based on its length:
                # 3 = Bond, 4 = Angle, 5 = Dihedral, 6 = Improper
                constraintType = ['bond', 'angle', 'dihedral', 'improper']
                thisMonomerDictionary[constraintType[len(constraint) - 3]].append(constraint)
            # Finally, increment the atom IDs to take into account previous monomers in this molecule and then update the AADictionary.
            # Note that the ghost dictionary bond was already updated to have the correct realAtom AAID for this molecule when the bond was created. Therefore, leave the ghost dictionary unchanged.
            thisMonomerDictionary, ghostDictionary = helperFunctions.incrementAtomIDs(thisMonomerDictionary, ghostDictionary, noAtomsInMolecule, modifyGhostDictionary=False)
            noAtomsInMolecule += len(thisMonomerDictionary['type'])
            currentMonomerIndex += 1
            # Update the current AA dictionary with this monomer
            AADictionary = self.updateMoleculeDictionary(thisMonomerDictionary, AADictionary)
        # All Monomers sorted, now for the final bits
        AADictionary['natoms'] = noAtomsInMolecule
        for key in ['lx', 'ly', 'lz']:
            AADictionary[key] = thisMonomerDictionary[key]
        # Now we terminate the molecules using the technique in the addHydrogensToUA analysis script
        newHydrogenData = []
        for atomIndex, atomType in enumerate(AADictionary['type']):
            if atomType not in self.moleculeTerminatingConnections.keys():
                continue
            bondedAAIDs = []
            # Iterate over all termination connections defined for this atomType (in case we are trying to do something mega complicated)
            for connectionInfo in self.moleculeTerminatingConnections[atomType]:
                for [bondName, AAID1, AAID2] in AADictionary['bond']:
                    if AAID1 == atomIndex:
                        if AAID2 not in bondedAAIDs:
                            bondedAAIDs.append(AAID2)
                    elif AAID2 == atomIndex:
                        if AAID1 not in bondedAAIDs:
                            bondedAAIDs.append(AAID1)
                if len(bondedAAIDs) != connectionInfo[0]:
                    continue
                newHydrogenPositions = helperFunctions.getTerminatingPositions(AADictionary['unwrapped_position'][atomIndex], [AADictionary['unwrapped_position'][bondedAAID] for bondedAAID in bondedAAIDs], 1)
                for hydrogenPosition in newHydrogenPositions:
                    newHydrogenData.append([atomIndex, list(hydrogenPosition)])
        AADictionary = self.addTerminatingToMolecule(AADictionary, newHydrogenData)
        AADictionary = helperFunctions.addWrappedPositions(AADictionary)
        AADictionary = helperFunctions.addMasses(AADictionary)
        AADictionary = helperFunctions.addDiameters(AADictionary)
        # Now the molecule is done, we need to add on the correct identifying numbers for all the bonds, angles and dihedrals
        # (just as we did between monomers) for the other molecules in the system, so that they all connect to the right atoms
        # Note that here we need to increment the '_'+ATOMIDs in the ghost dictionary to take into account the number of molecules.
        AADictionary, ghostDictionary = helperFunctions.incrementAtomIDs(AADictionary, ghostDictionary, self.noAtomsInMorphology, modifyGhostDictionary=True)
        return AADictionary, atomIDLookupTable, ghostDictionary

    def addTerminatingToMolecule(self, AADictionary, newHydrogenData):
        hydrogenID = len(AADictionary['type'])
        for hydrogen in newHydrogenData:
            # hydrogen has the form [BondedAtomID, [position]]
            AADictionary['unwrapped_position'].append([coord for coord in hydrogen[1]])
            AADictionary['type'].append('H1')
            AADictionary['body'].append(-1)
            AADictionary['charge'].append(0.0)
            AADictionary['bond'].append([AADictionary['type'][hydrogen[0]] + '-H1', hydrogen[0], hydrogenID])
            AADictionary['natoms'] += 1
            hydrogenID += 1
        return AADictionary

    def totalPermittedAtoms(self, monomerList):
        # Work out how many atoms we have in the molecule so that we don't create
        # any constraints including atoms outside this molecule
        totalPermittedAtoms = 0
        for monomer in monomerList:
            for CGSiteID in monomer:
                CGSiteType = self.CGDictionary['type'][CGSiteID]
                totalPermittedAtoms += len(self.CGToTemplateAAIDs[CGSiteType])
        return totalPermittedAtoms

    def sortIntoMonomers(self, typeListSequence):
        monomerList = []
        moleculeSiteIDs = copy.deepcopy(self.siteIDs)
        # Iterate over the entire bondlist until it's done
        bondList = copy.deepcopy(self.CGDictionary['bond'])
        while len(moleculeSiteIDs) > 0:
            # Add the first atom to the first monomer
            thisMonomer = []
            monomerTypesAdded = [typeListSequence[moleculeSiteIDs[0]]]
            thisMonomer.append(moleculeSiteIDs[0])
            addedNewSite = True
            while addedNewSite is True:
                # Keep adding new, connected atoms until we can't add any more
                addedNewSite = False
                bondPopList = []
                # Find bonded atoms that are not of the same type
                for bondNo, bond in enumerate(bondList):
                    if (bond[1] in thisMonomer) and (bond[2] not in thisMonomer) and (typeListSequence[bond[2]] not in monomerTypesAdded):
                        thisMonomer.append(bond[2])
                        monomerTypesAdded.append(typeListSequence[bond[2]])
                        addedNewSite = True
                    elif (bond[2] in thisMonomer) and (bond[1] not in thisMonomer) and (typeListSequence[bond[1]] not in monomerTypesAdded):
                        thisMonomer.append(bond[1])
                        monomerTypesAdded.append(typeListSequence[bond[1]])
                        addedNewSite = True
                    elif (bond[1] in thisMonomer) and (bond[2] in thisMonomer):
                        pass
                    else:
                        continue
                    bondPopList.append(bondNo)
                # Remove the bonds we've already considered
                bondPopList.sort(reverse=True)
                for bondIndex in bondPopList:
                    bondList.pop(bondIndex)
            for atomIndex in thisMonomer:
                moleculeSiteIDs.remove(atomIndex)
            monomerList.append(thisMonomer)
        monomerTypesList = []
        for monomer in monomerList:
            monomerTypesList.append([])
            for atom in monomer:
                monomerTypesList[-1].append(typeListSequence[atom])
        return monomerList

    def updateMoleculeDictionary(self, currentMonomerDictionary, AADictionary):
        # Update AADictionary with all of the values in currentMonomerDictionary,
        # except ths system dimensions which will be sorted later
        keyList = list(AADictionary.keys())
        keyList.remove('lx')
        keyList.remove('ly')
        keyList.remove('lz')
        keyList.remove('xy')
        keyList.remove('xz')
        keyList.remove('yz')
        for key in keyList:
            for value in currentMonomerDictionary[key]:
                AADictionary[key].append(value)
        return AADictionary

    def getAATemplatePosition(self, CGToTemplateAAIDs):
        CGCoMs = {}
        # For each CG site, determine the types and positions so we can calculate the COM
        for siteName in list(CGToTemplateAAIDs.keys()):
            atomIDs = CGToTemplateAAIDs[siteName]
            AATemplate = self.AATemplatesDictionary[siteName]
            # If the key's length is zero, then add all the atoms from the template
            if len(atomIDs) == 0:
                atomIDs = list(np.arange(len(AATemplate['type'])))
                # Update self.CGToTemplateAAIDs with these for later on
                CGToTemplateAAIDs[siteName] = atomIDs
            sitePositions = []
            siteTypes = []
            for atomID in atomIDs:
                siteTypes.append(AATemplate['type'][atomID])
                sitePositions.append(AATemplate['unwrapped_position'][atomID])
            # These output as numpy arrays because we can't do maths with lists
            CGCoMs[siteName] = helperFunctions.calcCOM(sitePositions, listOfAtomTypes=siteTypes)
        return CGCoMs, CGToTemplateAAIDs