import arcpy

#input layers
#Definition query down to the County in both the road inventory and the ARNOLD dataset, Handel only one county at a time
#definition query will be handeled on the table layer level
roadInventoryLayer = ""
ARNOLDLayer = ""

outpath = "C:\\scratch\\test.csv"
multiplicationFactor = 10000

roadIdsList = []

#Get all of the road inventory segements for a single section for that county = multiply by 10000 and add together
roadInvDict = {}
with arcpy.da.SearchCursor(roadInventoryLayer, ['AH_roadid', "RoadLength" ]) as roadInvCur:
    for segement in roadInvCur:
        selectedRoadID = segement[0]
        selectedRoadLength = segement[1]
        if selectedRoadID in roadInvDict:
            roadInvDict[selectedRoadID] = int((selectedRoadLength * multiplicationFactor)) + roadInvDict[selectedRoadID][0]
        else:
            roadInvDict[selectedRoadID] = int((selectedRoadLength * multiplicationFactor))
        roadIdsList.appned(selectedRoadID)
            
            
#Get all arnold segments for a single section for that county - multiply by 10000 and add together (multiplication is there to avoid floating point rounding errors
arnoldDict = {}
with arcpy.da.SearchCursor(ARNOLDLayer, ['AH_RoadID', "AH_Length" ]) as arnoldCur:
    for segment in arnoldCur:
        selectedRoadID = segement[0]
        selectedRoadLength = segement[1]
        if segement[0] in arnoldDict:
            arnoldDict[selectedRoadID] = int((selectedRoadLength * multiplicationFactor)) + arnoldDict[selectedRoadID]
        else:
            arnoldDict[selectedRoadID] = int((selectedRoadLength * multiplicationFactor))
            
        roadIdsList.appned(selectedRoadID)
        
roadIdsList = List(Set(roadIdsList))




        
#Generate an output list with the following fields AH_RoadID, ARNOLD Milage, RoadInventory Milage, Difference, Error
outputList = ["AH_RoadID" , "ARNOLD_Milage" , "RoadInv_Milage", "Milage_Diff" , "Error"]

for roadID in roadIdsList:
    #Merge the two lists together according to road ID, divide the road milage according to the multiplication factor to avoid issues with floating point addition
    
    if roadID in arnoldDict:
        arnoldMiles = float(arnoldDict[roadID]) / multiplicationFactor
    else:
        arnoldMiles = - 1
        error = "Missing from ARNOLD"
        
    if roadID in roadInvDict:
        roadInvMiles = float(roadInvDict[roadID]) / multiplicationFactor
    else:
        roadInvMiles = - 1
        error = "Missing from Road Inventory"
    
    #output table contains the following errors codes
    # - Missing from Road Inventory
    # - Missing from ARNOLD
    # - Road Inventory and Arnold milage do not match
    
    if roadID in arnoldDict and roadID in roadInvDict:
        milesDiff = (arnoldDict[roadID] - roadInvDict[roadID]) / multiplicationFactor
        if milesDiff == 0:
            error = "No Error"
        else:
            error = "Milages Differs"
    
    outputRow = [roadID, arnoldMiles , roadInvMiles, milesDiff, error]
    
    outputList.append(outputRow)

print "write CSV file"
#open and set the csv file for writting
opener = open(csvPath, "w")
csvWriter = csv.writer(opener, "windcsv")

for row in outputList:
    csvWriter.writerow(row)
    
#close out the csv file
del csvWriter
opener.close()
