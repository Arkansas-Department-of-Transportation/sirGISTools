import arcpy, os, os.path, csv
from collections import Counter
#register the dialect for windows csv
csv.register_dialect("windcsv", lineterminator="\n")


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "SirGISTools"
        self.alias = "SIR GIS Tools"
        
        # List of tool classes associated with this toolbox
        self.tools = [MeetingLocationSpreadsheet, ArnoldReconciliation, UIDCalculate, OffAndOnSystemMerge]
        
class ArnoldReconciliation(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "ARNOLD Reconciliation"
        self.description = "Generates a reconciliation spreadsheet which shows differences between the Road Inventory and ARNOLD datasets. Is not intended to be run on the entire datset. Designed to be run on a single or a few counties at a time"
        self.canRunInBackground = False
        
    def getParameterInfo(self):
        """Define parameter definitions"""
        #ARNOLD Table
        arnoldTable = arcpy.Parameter(name="arnoldTable" ,
            displayName="ARNOLD Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
            
        # Road ID Field from ARNOLD Table
        roadIDARNOLDTable = arcpy.Parameter(name="roadIDARNOLDTable" ,
            displayName="Road ID ARNOLD Table",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        roadIDARNOLDTable.parameterDependencies = [arnoldTable.name]
        
        # Road Legnth Field from ARNOLD Table
        roadLengthARNOLDTable = arcpy.Parameter(name="roadLengthARNOLDTable" ,
            displayName="Road Length ARNOLD Table",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        roadLengthARNOLDTable.parameterDependencies = [arnoldTable.name]
            
            
            
            
        #Road Inventory Table
        roadInvTable = arcpy.Parameter(name="roadInvTable" ,
            displayName="Road Inventory Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
            
        # Road ID Road Inventory
        roadIDRoadInvTable = arcpy.Parameter(name="roadIDRoadInvTable" ,
            displayName="road ID Road Inv Table",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        roadIDRoadInvTable.parameterDependencies = [roadInvTable.name]
        
        # Road Length from Road Inventory
        roadLengthRoadInvTable = arcpy.Parameter(name="roadLengthRoadInvTable" ,
            displayName="Road Length Road Inventory Table",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        roadLengthRoadInvTable.parameterDependencies = [roadInvTable.name]
        
        #csv output table
        csvPath = arcpy.Parameter(name="csvPath" ,
            displayName="csvPath",
            direction="Output",
            datatype="DEFile",
            parameterType="Required")
         
        return [arnoldTable, roadIDARNOLDTable, roadLengthARNOLDTable, roadInvTable, roadIDRoadInvTable, roadLengthRoadInvTable, csvPath]
    
    def updateParameters(self, parameters):
        """Update the parameter information based on the values inside of the GP dialog box"""
        
        if parameters[2].value:
            extension = str(os.path.splitext(parameters[2].valueAsText)[1])
            if  extension == "csv" or extension == "CSV":
                pass
            elif extension == "" or extension == None or extension == "None" or extension == "none" or extension == "NONE" or len(extension) > 0:
                parameters[2].value = os.path.splitext(parameters[2].valueAsText)[0] + ".csv"
            else:
                pass
    
    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        messages.AddMessage("Gathering Parameters")
        arnoldTable = parameters[0].Value
        roadIDFieldArnoldTable = parameters[1].valueAsText
        roadLengthFieldArnoldTable = parameters[2].valueAsText
        
        roadInvTable = parameters[3].Value
        roadIDFieldRoadInvTable = parameters[4].valueAsText
        roadLengthFieldRoadInvTable = parameters[5].valueAsText
        csvPath = parameters[6].valueAsText
        
        multiplicationFactor = 10000
        
        roadIdsList = []
        
        #Get all of the road inventory segements for a single section for that county = multiply by 10000 and add together
        messages.AddMessage("Reading Road Inventory Dataset")
        roadInvDict = {}
        with arcpy.da.SearchCursor(roadInvTable, [roadIDFieldRoadInvTable, roadLengthFieldRoadInvTable ]) as roadInvCur:
            for roadInvSegement in roadInvCur:
                selectedRoadInvRoadID = roadInvSegement[0]
                selectedRoadInvLength = roadInvSegement[1]
                if selectedRoadInvRoadID in roadInvDict:
                    roadInvDict[selectedRoadInvRoadID] = selectedRoadInvLength + roadInvDict[selectedRoadInvRoadID]
                else:
                    roadInvDict[selectedRoadInvRoadID] = selectedRoadInvLength
                roadIdsList.append(selectedRoadInvRoadID)
                    
                    
        #Get all arnold segments for a single section for that county - multiply by 10000 and add together (multiplication is there to avoid floating point rounding errors
        messages.AddMessage("Reading ARNOLD Dataset")
        arnoldDict = {}
        with arcpy.da.SearchCursor(arnoldTable, [roadIDFieldArnoldTable, roadLengthFieldArnoldTable ]) as arnoldCur:
            for arnoldSegment in arnoldCur:
                selectedARNOLDRoadID = arnoldSegment[0]
                selectedARNOLDRoadLength = arnoldSegment[1]
                
                if selectedARNOLDRoadID in arnoldDict:
                    arnoldDict[selectedARNOLDRoadID] = selectedARNOLDRoadLength + arnoldDict[selectedARNOLDRoadID]
                else:
                    arnoldDict[selectedARNOLDRoadID] = selectedARNOLDRoadLength
                    
                roadIdsList.append(selectedARNOLDRoadID)
                
        
                
        roadIdsList = list(set(roadIdsList))
        
        #for debugging purposes
        messages.AddMessage("Road Inventory Records in Road summarized are " + str(len(roadInvDict)) )
        messages.AddMessage(roadInvDict)
        messages.AddMessage("ARNOLD Records in Road summarized are " + str(len(arnoldDict)) )
        messages.AddMessage(arnoldDict)
        messages.AddMessage("Final output dataset will be " + str(len(roadIdsList)) )
        
        
        messages.AddMessage("Building Virtual reconciliation table")
        #Generate an output list with the following fields AH_RoadID, ARNOLD Milage, RoadInventory Milage, Difference, Error
        outputList = [["AH_RoadID" , "ARNOLD_Milage" , "RoadInv_Milage", "Milage_Diff" , "Error"]]
        
        totalMilesMissingFromARNOLD = 0
        totalMilesMissingFromRoadInventory = 0
        totalMilesofExistingSectionNotMatching = 0
        
        for roadID in roadIdsList:
            #Merge the two lists together according to road ID, divide the road milage according to the multiplication factor to avoid issues with floating point addition
            
            if roadID in arnoldDict:
                arnoldMiles = round(arnoldDict[roadID], 3)
            else:
                arnoldMiles = - 1
                error = "Missing from ARNOLD"
                totalMilesMissingFromARNOLD += roadInvDict[roadID]
                
            if roadID in roadInvDict:
                roadInvMiles = round(roadInvDict[roadID], 3)
            else:
                roadInvMiles = - 1
                error = "Missing from Road Inventory"
                totalMilesMissingFromRoadInventory += arnoldDict[roadID]
            
            #output table contains the following errors codes
            # - Missing from Road Inventory
            # - Missing from ARNOLD
            # - Road Inventory and Arnold milage do not match
            
            if roadID in arnoldDict and roadID in roadInvDict:
                milesDiff = abs(round( (arnoldDict[roadID] - roadInvDict[roadID]) , 3))
                if milesDiff == 0:
                    error = "No Error"
                elif milesDiff > 0 and milesDiff <= 0.003:
                    error = "Likely Rounding Error"
                    totalMilesofExistingSectionNotMatching += abs(arnoldDict[roadID] - roadInvDict[roadID])
                else:
                    error = "Milages Differs"
                    totalMilesofExistingSectionNotMatching += abs(arnoldDict[roadID] - roadInvDict[roadID])
            else:
                milesDiff = 0
                    
            outputRow = [roadID, arnoldMiles , str(roadInvMiles), str(milesDiff), error]
            
            outputList.append(outputRow)
        
        messages.AddMessage("Writing/saving output table")
        print "write CSV file"
        #open and set the csv file for writting
        opener = open(csvPath, "w")
        csvWriter = csv.writer(opener, "windcsv")
        
        for row in outputList:
            csvWriter.writerow(row)
            
        #close out the csv file
        del csvWriter
        opener.close()
        
        totalMilesMissingFromARNOLD = round( totalMilesMissingFromARNOLD , 3 )
        messages.AddMessage("Miles missing from ARNOLD: " + str(totalMilesMissingFromARNOLD))
        totalMilesMissingFromRoadInventory = round( totalMilesMissingFromRoadInventory, 3)
        messages.AddMessage("Miles missing from Road Inventory: " + str(totalMilesMissingFromRoadInventory))
        totalMilesofExistingSectionNotMatching = round(totalMilesofExistingSectionNotMatching , 3)
        messages.AddMessage("Miles of existing section differing between : " + str(totalMilesMissingFromRoadInventory))
        
class UIDCalculate(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "UID Calculate"
        self.description = "Adds UID values for a field where some records do not have that id"
        self.canRunInBackground = False
        
        
    def getParameterInfo(self):
        """Define parameter definitions"""
        
        # Table
        table = arcpy.Parameter(name="table" ,
            displayName="Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
            
        # UID field
        uIDField = arcpy.Parameter(name="uIDField" ,
            displayName="UID Field",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        uIDField.parameterDependencies = [table.name]
        
        return [table, uIDField]
        
    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        table = parameters[0].Value
        uIDField = parameters[1].valueAsText
        
        messages.AddMessage("finding highest ID")
        #open cusor
        #find max id
        highestnumber = 0
        with arcpy.da.SearchCursor(table, [uIDField ]) as cursor:
            for row in cursor:
                if row[0] > highestnumber:
                    highestnumber = row[0]
                    
                    
        #running list of unique ids
        messages.AddMessage("updating uID Field")
        uniqueIds = []
        with arcpy.da.UpdateCursor(table, [uIDField ] ) as cursor:
            for row in cursor:
                for uniqueID in uniqueIds:
                    #if the value is duplicate with an existing ID
                    if uniqueID == row[0] or uniqueID == None or uniqueID == "NULL" or uniqueID == "Null" or uniqueID == 0 or uniqueID == "" or uniqueID == " " or uniqueID < 0:
                        #need to give record a new id that is actually unique
                        highestnumber =+ 1
                        row[0] = highestnumber
                        
                        uniqueIds.append(row[0])
                        cursor.updateRow(row)
                    else:
                        uniqueIds.append(row[0])
        
        
        
class MeetingLocationSpreadsheet(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Meeting Spreadsheet"
        self.description = "Generates a meeting spreadsheet given a unit feature class and a meeting buffer feature class. The Meeting spreadsheet will contain fields for Meeting Location, Unit Name, and Number of Duplicates. The unit feature class is intended to be the layer of the municipalities, congressional districts, house districts or senate districts the meeting was indented to cover. The meeting location buffer layer is indented to be the already buffered meeting locations."
        self.canRunInBackground = False
        
    def updateParameters(self, parameters):
        """Update the parameter information based on the values inside of the GP dialog box"""
        
        if parameters[4].value:
            extension = str(os.path.splitext(parameters[4].valueAsText)[1])
            if  extension == "csv" or extension == "CSV":
                pass
            elif extension == "" or extension == None or extension == "None" or extension == "none" or extension == "NONE" or len(extension) > 0:
                parameters[4].value = os.path.splitext(parameters[4].valueAsText)[0] + ".csv"
            else:
                pass
                
    def getParameterInfo(self):
        """Define parameter definitions"""
        
        unitFeatureClass = arcpy.Parameter(name="unitFeatureClass" ,
            displayName="Unit Feature Class",
            direction="Input",
            datatype="GPFeatureLayer",
            parameterType="Required")
            
        unitNameField = arcpy.Parameter(name="unitNameField" ,
            displayName="Unit Name/Label Field",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        unitNameField.parameterDependencies = [unitFeatureClass.name]
        
        meetingBufferFeatureClass = arcpy.Parameter(name="meetingBufferFeatureClassFeatureClass" ,
            displayName="Meeting Location Buffer Feature Class",
            direction="Input",
            datatype="GPFeatureLayer",
            parameterType="Required")
            
        meetingLocationNameField = arcpy.Parameter(name="meetingLocationNameField" ,
            displayName="Meeting Location Name Field",
            direction="Input",
            datatype="Field",
            parameterType="Required")
            
        meetingLocationNameField.parameterDependencies = [meetingBufferFeatureClass.name]
        
        
        csvPath = arcpy.Parameter(name="csvPath" ,
            displayName="csvPath",
            direction="Output",
            datatype="DEFile",
            parameterType="Required")
            
            
        return [unitFeatureClass, unitNameField, meetingBufferFeatureClass, meetingLocationNameField, csvPath]

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        messages.AddMessage("Collecting Parameters")
        #changes the parameter object which returns GP parameter information into several variables rather than one with arbitrary indices.
        unitFeatureClass = parameters[0].Value
        unitNameField = parameters[1].valueAsText
        meetingBufferFeatureClass = parameters[2].Value
        meetingLocationNameField = parameters[3].valueAsText
        csvPath = parameters[4].valueAsText
        
        #used for embedding the county field into the final tabular result
        messages.AddMessage("Connecting to counties dataset")
        countiesPath = r"\\san1\SIR\SystemInformation\System Information Group\GIS\MiscTools\sirGISTools\COUNTIES_AHTD.lyr"
        countiesFeatureClass = arcpy.MakeFeatureLayer_management(countiesPath)
        
        
        #create an empty list of lists with the following fields, Meeting location, City, county, duplicates
        resultList = []
        resultList.append(["Meeting Location" , "Unit Name", "County", "Number of Duplicates"])
        
        #The counties layer is copied from the State GIS Office Rest Service into an in memory feature class to improve cursor looping speed in future steps.
        messages.AddMessage("Making in memory copy of counties feature class")
        CountiesFeatureClassInMemory = r"in_memory\counties"
        arcpy.CopyFeatures_management(countiesFeatureClass, CountiesFeatureClassInMemory)
        
        
        #Loop through each unit and assign it a county or counties and store in a list object
        messages.AddMessage("Assinging counties and units together")
        unitList = []
        with arcpy.da.SearchCursor(unitFeatureClass, ['SHAPE@', unitNameField ]) as unitCur:
            for unit in unitCur:
                #unit may cover several different counties. A list is needed to combine multiple counties into a single string after looping through the entire counties dataset.
                countyList = []
                with arcpy.da.SearchCursor(CountiesFeatureClassInMemory, ['SHAPE@', "county_nam"]) as countyCur:
                    for county in countyCur:
                        if county[0].disjoint(unit[0]) == False:#Check to see if the two geometry objects intersect eachother at all.
                            countyList.append(str(county[1]))
                
                #place holder string which is placed outside of the scope of the for loop so the end result of the for loop can be added into the unit list.
                countyString = ""
                if len(countyList) > 1:
                    for selectedCounty in countyList:
                        countyString += selectedCounty + ", "
                    countyString = countyString[0: len(countyString) - 2]
                elif len(countyList) == 1:
                    countyString = countyList[0]
                
                messages.AddMessage("     Unit: " + unit[1] + " - " + countyString + " County(s)")
                #order is geometry object, Unit Name, County(s)
                unitList.append([unit[0], str(unit[1]), countyString])
                
                
        messages.AddMessage("Assigned counties to each unit field")
        #if there are no features inside of the unit feature class warn the end user before the error messages later on make it hard to understand the root cause of the issue.
        if len(unitList) == 0:
            messages.addWarningMessage("There are not any units contained in the units feature class")
        else:
            messages.AddMessage(unitList)
        
        messages.AddMessage("Comparing Buffer Area with Unit Polygons")
        
        #find out and create records for each time a buffer intersects a unit feature.
        unitNameListWithDuplicates = []
        with arcpy.da.SearchCursor(meetingBufferFeatureClass, ['SHAPE@', meetingLocationNameField]) as BufferCur:
            for rowBuffer in BufferCur:
                #iterate through each unit boundary
                for unitRow in unitList:
                    #perform a does contain if statement
                    if unitRow[0].disjoint(rowBuffer[0]) == False:
                        #Meeting Location, Unit Name, Unit County
                        resultList.append([rowBuffer[1], unitRow[1], unitRow[2], 0])
                        unitNameListWithDuplicates.append(unitRow[1])
        messages.AddMessage(unitNameListWithDuplicates)
                        
                        
        #find all of the duplicates and give the appropriate number of things for each
        messages.AddMessage("Calculating Duplicates.....Duplicates list is.....:")
        messages.AddMessage(unitNameListWithDuplicates)
        
        #determine how many duplicates exist inside of the table and add the number at the end of the correct record's last field
        countOfDuplicatesDict = Counter(unitNameListWithDuplicates)
        for key in countOfDuplicatesDict:
            for resultRow in resultList:
                if resultRow[1] == key:
                    resultRow[3] = countOfDuplicatesDict[key]
                    
        
        #write the result to a CSV file
        messages.AddMessage("Writting CSV File output")
        #open and set the csv file for writting
        opener = open(csvPath, "w")
        csvWriter = csv.writer(opener, "windcsv")
        
        for row in resultList:
            csvWriter.writerow(row)
    
        #close out the csv file
        del csvWriter
        opener.close()
                
            
        messages.AddMessage("Finished making CSV file")
        
class UpdateDissolve(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Update APHN Dissolve Feature Class"
        self.description = "Updates the APHN Dissolve layer feature class when given a Route Event for Road Inventory"
        
    def getParameterInfo(self):
        """Define parameter definitions"""
        #input feature class
        inputFeatureLayer = arcpy.Parameter(name="inputFeatureLayer" ,
            displayName="Input Feature Layer",
            direction="Input",
            datatype="GPFeatureLayer",
            parameterType="Required")
            
        #Append Feature Class
        AppendFeatureLayer = arcpy.Parameter(name="AppendFeatureLayer" ,
            displayName="Append Feature Layer",
            direction="Input",
            datatype="GPFeatureLayer",
            parameterType="Required")
            
        #dissolve Type
        dissolveType = arcpy.Parameter(name="dissolveType",
            displayName="Dissolve Type",
            direction="Input",
            datatype="GPString",
            parameterType="Required")
            
        dissolveType.filter.list = ["AHPN", "NHS", "RouteSign", "Functional Class", "Special System"]
            
        return [inputFeatureLayer, AppendFeatureLayer]
        
    def execute(self, parameters, messages):
        """The source code of the tool."""
        routeEvent = parameters[0].Value
        appendFeatureClass = parameters[1].Value
        dissolveType = parameters[2].valueAsText
        
        messages.AddMessage("Source Layer is being created")
        sourceLayer = "Source_layer"
        arcpy.MakeFeatureLayer_management(routeEvent, sourceLayer)
        
        #select the correct features in the route event
        messages.AddMessage("Selecting Attributes for dissolve layer")
        sqlStatement = ""
        if dissolveType == u"AHPN":
            sql = "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1 AND SpecialSystems <> 1"
        elif dissolveType == u"NHS":
            sql = "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1 AND NHS <> 0"
        elif dissolveType == u"RouteSign":
            sql = "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1"
        elif dissolveType == u"Functional Class":
            sql = "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1 AND FunctionalClass <> 7"
        elif dissolveType == u"Special System":
            sql = "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1 AND SpecialSystems <> 1"
        else:
            raise Exception
        
        arcpy.SelectLayerByAttribute_management(sourceLayer, "NEW_SELECTION", "TypeRoad IN( 1 , 2 ) AND SystemStatus = 1 AND SpecialSystems <> 1")
        
        dissolveTemp = "C:\\scratch\\test.shp"
        
        #run the dissolve tool
        messages.AddMessage("Creating Dissolve Layer")
        arcpy.Dissolve(sourceLayer, dissolveTemp , ["County", "Route", "Sectn", "Logmile", "Direction", "AH_roadid"], ["Logmile", "EndLogmile"])
        
        
        #map the result to a new field setup which matches the FC Schema
        #arcpy.DeleteFeatures_management(appendFeatureClass)
        #Append the resulting matching schema FC to the web version
        #
        
        

class OffAndOnSystemMerge(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Off and On System Merge"
        self.description = "Merges tables for on and off system into a single table"
        self.canRunInBackground = False
    
    def getParameterInfo(self):
        """Define parameter definitions"""
        
        #On system road inventory table
        outMileageTable = arcpy.Parameter(name="outMileageTable" ,
            displayName="Out Miles Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
        
        #Off system road inventory table
        offSystemTable = arcpy.Parameter(name="offSystemTable" ,
            displayName="Off System Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
            
        #Intermidate table - map on system to new schema
        mergedTable = arcpy.Parameter(name="mergedTable" ,
            displayName="Merged Table",
            direction="Input",
            datatype="GPTableView",
            parameterType="Required")
        

        
        return [outMileageTable, offSystemTable, mergedTable]
    
    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        outMileageTable = parameters[0].Value
        offSystemTable = parameters[1].Value
        mergedTable = parameters[2].Value
        
        
        #Append on system road inventory table into the temp table
        #delete all off system records from the temp table
        #Use nested cursors to switch out content in the functional class field for everything within the on system
        #append all off system records into the new temp table
        #copy the dataset into the world location
        #empty out the temp table
        
        #Make a table view of outtable
        messages.AddMessage("Outmiles table view is being created")
        outMileageTableView = "OutmileageView"
        arcpy.MakeTableView_management(outMileageTable, outMileageTableView)
        
        messages.AddMessage("Appending outmiles table records into intermidate table")
        #append the information into a table with a schema matching the FC schema - the merge table
        schemaFieldMap = arcpy.FieldMappings()
        
        #Road ID
        roadIDFieldMap =  arcpy.FieldMap()
        roadIDFieldMap.addInputField(outMileageTableView, "AH_roadid")
        roadIDFieldMap.outputField.name = "AH_RoadID"
        schemaFieldMap.addFieldMap(roadIDFieldMap)
        
        #All Fields that are the same
        sameList = ["GovermentCode", "APHN",  
            "SystemStatus", "TypeRoad", "RouteSign", "Access", "TypeOperation", 
            "MedianType", "MedianWidth", "SurfaceType", "LaneWidth", "SurfaceWidth", 
            "RoadwayWidth", "ExtraLanes", "PSR", "CrewNumber", "SampleID",
            "IS_Structure", "HOV_Type", "Peak_Lanes", "Counter_Peak_Lanes",
            "Turn_Lanes_R", "Turn_Lanes_L", "Toll_Charged", "Signal_Type", "Pct_Green_Time",
            "Number_Signals", "Stop_Signs", "At_Grade_Other", "Median_Width", "Peak_Parking",
            "Widening_Potential", "Pct_Pass_Sight", "Year_Last_Construction", "Last_Overlay_Thickness",
            "Thickness_Rigid", "Thickness_Flexible", "Base_Type", "Base_Thickness", "YearIRI", "YearBuilt",
            "YearRecon", "RoughCode", "Widening_Obstacle", "Terrain", "UrbanAreaCode", "NHS"]
            
            
        for sameField in sameList:
            messages.AddMessage("Adding Field to field maps " + sameField)
            tempFieldMap = arcpy.FieldMap()
            tempFieldMap.addInputField(outMileageTableView, sameField)
            tempFieldMap.outputField.name = sameField
            schemaFieldMap.addFieldMap(tempFieldMap)
            
        differingFieldsList = [["HPMSSSection", "HPMS_Section" ], 
            ["SpecialSystem" , "SpecialSystems"],
            ["NumberLanes", "Total_Lanes"],
            ["AvgDailyTraffic", "ADT"],
            ["RoadLength", "AH_Length"],
            ["District" , "AH_District"],
            ["Speed_Limit", "Speedlimit"],
            ["Name" , "Comment"],
            ["RightShldSur", "RightShoulderSurface"],
            ["LeftShldSur", "LeftShoulderSurface"],
            ["RightSHldWidth", "RightShoulderWidth"],
            ["LeftSHldWidth", "LeftShoulderWidth"],
            ["FuncClass" , "FunctionalClass"],
            ["GovermentCode" , "GovernmentCode"],
            ["Logmile" , "AH_BLM" ],
            ["EndLogmile" , "AH_ELM"]
            ]
            
        for fieldPair in differingFieldsList:
            messages.AddMessage( "Add Field for " + fieldPair[0])
            tempFieldmap = arcpy.FieldMap()
            tempFieldmap.addInputField(outMileageTableView, fieldPair[0])
            outputField = tempFieldmap.outputField
            outputField.name = fieldPair[1]
            tempFieldmap.outputField = outputField
            schemaFieldMap.addFieldMap(tempFieldmap)
            
        '''    
        #ADT - ADT_Year, YearADT
        adtYearFieldMap = arcpy.FieldMap()
        adtYearFieldMap.addInputField(outMileageTableView, "YearADT")
        adtOutField = adtYearFieldMap.outputField
        adtOutField.name = "ADT_Year"
        adtOutField.type = "SmallInteger"
        adtYearFieldMap.outputField = adtOutField
        schemaFieldMap.addFieldMap(adtYearFieldMap)
        
        
        #HPMS Section
        hpmsSectionFieldMap = arcpy.FieldMap()
        hpmsSectionFieldMap.addInputField(outMileageTableView, "HPMSSSection")
        hpmsSectionFieldMap.outputField.name = "HPMS_Section"
        schemaFieldMap.addFieldMap(hpmsSectionFieldMap)
        
            
        #"SpecialSystem SpecialSystems",
        specialSystemsFieldMap = arcpy.FieldMap()
        specialSystemsFieldMap.addInputField(outMileageTableView, "SpecialSystem")
        specialSystemOutputField = specialSystemsFieldMap.outputField
        specialSystemOutputField.name = "SpecialSystems"
        specialSystemsFieldMap.outputField = specialSystemOutputField
        schemaFieldMap.addFieldMap(specialSystemsFieldMap)
        
        #Lanes - Total_Lanes, NumberLanes
        lanesFieldMap = arcpy.FieldMap()
        lanesFieldMap.addInputField(outMileageTableView, "NumberLanes")
        lanesFieldOutputField = lanesFieldMap.outputField
        lanesFieldOutputField.name = "Total_Lanes"
        lanesFieldMap.outputField = lanesFieldOutputField
        schemaFieldMap.addFieldMap(lanesFieldMap)
        
        #ADT
        averageDailyTrafficFieldMap = arcpy.FieldMap()
        averageDailyTrafficFieldMap.addInputField(outMileageTableView, "AvgDailyTraffic")
        averageDailyTrafficFieldMap.outputField.name = "ADT"
        outputField = averageDailyTrafficFieldMap.outputField
        averageDailyTrafficFieldMap 
        schemaFieldMap.addFieldMap(averageDailyTrafficFieldMap)
        

            
        #length , AH_Length, RoadLength
        lengthFieldMap = arcpy.FieldMap()
        lengthFieldMap.addInputField(outMileageTableView, "RoadLength")
        lengthFieldMap.outputField.name = "AH_Length"
        schemaFieldMap.addFieldMap(lengthFieldMap)
        
        #District
        districtFieldMap = arcpy.FieldMap()
        districtFieldMap.addInputField(outMileageTableView, "District")
        districtFieldMap.outputField.name = "AH_District"
        schemaFieldMap.addFieldMap(districtFieldMap)
        
        #Speed Limit
        speedLimitFieldMap = arcpy.FieldMap()
        speedLimitFieldMap.addInputField(outMileageTableView, "Speed_Limit")
        speedLimitFieldMap.outputField.name = "Speedlimit"
        schemaFieldMap.addFieldMap(speedLimitFieldMap)
        
        #Description Field
        DescriptionFieldMap = arcpy.FieldMap()
        DescriptionFieldMap.addInputField(outMileageTableView, "Name")
        DescriptionFieldMap.outputField.name = "Comment"
        schemaFieldMap.addFieldMap(DescriptionFieldMap)
            
        #RightShoulderSurface
        rightShoulderSurfaceFieldMap = arcpy.FieldMap()
        rightShoulderSurfaceFieldMap.addInputField(outMileageTableView, "RightShldSur")
        rightShoulderSurfaceFieldMap.outputField.name = "RightShoulderSurface"
        schemaFieldMap.addFieldMap(rightShoulderSurfaceFieldMap)
        
        #LeftShoulderSurface
        leftShoulderSurfaceFieldMap = arcpy.FieldMap()
        leftShoulderSurfaceFieldMap.addInputField(outMileageTableView, "LeftShldSur")
        leftShoulderSurfaceFieldMap.outputField.name = "LeftShoulderSurface"
        schemaFieldMap.addFieldMap(leftShoulderSurfaceFieldMap)
        
        #RightShoulderWidth
        rightShoulderWidthFieldMap = arcpy.FieldMap()
        rightShoulderWidthFieldMap.addInputField(outMileageTableView, "RightSHldWidth")
        rightShoulderWidthFieldMap.outputField.name = "RightShoulderWidth"
        schemaFieldMap.addFieldMap(rightShoulderWidthFieldMap)
        
        #LeftShoulderWidth
        leftShoulderWidthFieldMap = arcpy.FieldMap()
        leftShoulderWidthFieldMap.addInputField(outMileageTableView, "LeftSHldWidth")
        leftShoulderWidthFieldMap.outputField.name = "LeftShoulderWidth"
        schemaFieldMap.addFieldMap(leftShoulderWidthFieldMap)
        
        
        
        #functional Class Field
        FunctionalClassFieldMap = arcpy.FieldMap()
        FunctionalClassFieldMap.addInputField(outMileageTableView, "FuncClass")
        FunctionalClassFieldMap.outputField.name = "FunctionalClass"
        schemaFieldMap.addFieldMap(FunctionalClassFieldMap)'''
        
        arcpy.Append_management(outMileageTableView, mergedTable, "NO_TEST", schemaFieldMap)
        
        mergeTableView = "mergeTableView"
        arcpy.MakeTableView_management(mergedTable, mergeTableView)
        
        #select off system to be deleted
        messages.AddMessage("Selecting off system for deletion")
        arcpy.SelectLayerByAttribute_management(mergeTableView, "NEW_SELECTION", "NOT (RouteSign = 1 OR RouteSign = 2 OR RouteSign = 3)")
        
        messages.AddMessage("Records selected from area: " + str(int(arcpy.GetCount_management(mergeTableView).getOutput(0))))
        
        #delete off system records from out_mileage copy table
        messages.AddMessage("Deleting off system records")
        arcpy.DeleteRows_management(mergeTableView)
        
        #cursor through District, County, Section, Length, Direction and Route Fields. Derive the outputs according to ARNOLD ID
        with arcpy.da.UpdateCursor(mergeTableView, ["AH_RoadID", "AH_District", "AH_County", "AH_Route", "AH_Section", "LOG_DIRECTION", "AH_BLM", "AH_ELM", "AH_Length"]) as cursor:
            for row in cursor:
                arnoldIDElementsList = str(row[0]).split("x")
                
                if not (row[1] == None or row[1] == "None" or row[1] == "" or row[1] == "Null" or row[1] == "NULL"):
                    row[1] = str(row[1]).lstrip("0")#district
                
                if len(arnoldIDElementsList) == 4:
                    row[2] = arnoldIDElementsList[0]#County
                    row[3] = arnoldIDElementsList[1]#route
                    row[4] = arnoldIDElementsList[2]#section
                    row[5] = arnoldIDElementsList[3]#Log Direction
                
                if not (row[7] == None or row[6] == None):
                    row[8] = row[7] - row[6]#Length, subtract begining and end log miles
                
                cursor.updateRow(row)
        
        
        #Make table view of Road Inventory Geodatabase Table
        messages.AddMessage("Make a tableview")
        offSystemView = "offSystemView"
        arcpy.MakeTableView_management(offSystemTable, offSystemView)
        
        #select on system and delete it
        #messages.AddMessage("selecting the OFF system in the OFF system table")
        arcpy.SelectLayerByAttribute_management(offSystemView, "NEW_SELECTION", "NOT (RouteSign = 1 OR RouteSign = 2 OR RouteSign = 3)")
        #messages.AddMessage("Appending into merged table")
        #arcpy.TableToTable_conversion(offSystemTable, "C:\scratch\automation\UpdateTesting.gdb\OFFSystemTemp")
        #arcpy.Append_management("C:\scratch\automation\UpdateTesting.gdb\OFFSystemTemp", mergedTable, "NO_TEST")
        arcpy.Append_management(offSystemView, mergedTable)
       
        
        #append on system into off system table
        messages.AddMessage("Appending the intermidate table into the OFF system table")
        
        #create field maps
        
        
        #recalculate the unique id in the system table
        
        
class RoadGeomFix(object):
    def __init__(self):
        pass
        
    def execute(self):
        """The source code of the tool."""
        #Dissolve ARNOLD by Road ID for later processing
        #dissolve Road Inv by Road ID for later processing
        #loop through each dissolved Road Inv road ID
        #    search cursor (query) for ARNOLD dissolve geometry
        #    compare record geometry - if they do not match flag ARNOLD ID for later processing
        #    get ARNOLD dissole endpoints - assoiated with a road id
        #    get Road Inv dissolve endpoints - associated points with road id
        #    check to see if Road Inv endpoints overlap ARNOLD dissolved geometry
        #        If they overlap Road Inv is undershooting the endpoints
        #            use spatial selection on road inv based on ARNOLD dissolved segement's endpoint
        #            run trip line tool on road inv selection
        #            record information to error log as its running
        #            
        #        If they do not both overlap, Road Inv is overshooting the endpoints
        #            use spatial selection on road inv based on ARNOLD dissolved endpoint
        #            run extend line tool on selected data in road inv
        #            record infroamtion to error log as its running
        #    
        
        #