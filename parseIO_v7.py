import re
import pandas as pd
from openpyxl import load_workbook
import argparse
pd.options.display.max_rows = None

#讀入相關的參數
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--file", required=True, help="Path to the txt of the braod file.")
args = vars(ap.parse_args())

# 開啟檔案
def open_brd_file(filepath):
    f = open(filepath)
    return f

#用空格拆分每一行
def splitRow(string):
    string = string.split()
    return string

#刪除|開頭
def deleteRow1(string):
    pattern = re.compile(r"\|")
    delete = pattern.findall(string)
    return delete
#刪除- - -開頭
def deleteRow2(string):
    pattern = re.compile(r"^\-$")
    delete = pattern.findall(string)
    return delete

#找到D開頭
def findD(string):
    pattern = re.compile(r"^D")
    locationD = pattern.findall(string)
    return locationD

    # 存excel
def save_excel(write, df, sheetName):
#     df = pd.DataFrame(datalist)
    df.to_excel(write, sheet_name=f'{sheetName}', index=False)

#刪多餘的raw
def deleteNullVIAROW(df):
    for i in range(df.shape[0]):
        if df.loc[i, "location"] == "VIA" and df.loc[i, "gap"] == 0.0:
            df.drop(i, axis=0, inplace=True)
            
#這一份txt total的path 數量
def branchPathNum(df):
    #扣掉net name/start_end/total length
    maxPathNum = int((df.shape[1] - 7) / 2)
    return maxPathNum


#CODE#########

#step1: 開啟檔案
filepath = args["file"]
try:
    f = open_brd_file(filepath)
    print(f"step1: Open file. (File name: {filepath}) -DONE")
except:
    print(f"File is not exit, check file name.")

#step2: 刪除不必要行數
rawData = []
SQS = []
summary = []
netNameList = []

for i in f:
    i = i.replace("\n","")#去掉換行符號
    row = splitRow(i)

    if not deleteRow1(row[0]):
        if not deleteRow2(row[0]):
            rawData.append(row)
print(f"step2: Clear excess rows. -DONE")

#step3: 整理成需要的格式
for i in rawData:
#     if len(i) == 1: #netname那一行

    if len(i) < 3: #netname那一行 ######################### TODO這行應該要改
        data = {} #清空data
        netName = i[0]
        
        netNameList.append(netName) #建立netnamelist
    elif i[-1] == "0.000": #找到location

        data = {} #清空 

        D = findD(i[0])
        if not D:
            try:
                location, length = i[0].replace("*", ""), float(i[-1])
                data.update({"net_name" : netName, "location" : location, "length": length, "layer": ""})
            except:
                print(netName," has error.")
            
            SQS.append(data)
    elif i[-1] == "mils": #找到TOTAL
        data = {} #清空
        ttlLength = float(i[3])
        data.update({"net_name" : netName, "total_length" : ttlLength})
        summary.append(data)
        
    else:
        data = {} #清空 

        D = findD(i[0])
        if not D:
            try:
                location, length, layer = i[0].replace("*", ""), float(i[-2]), i[-1]
                data.update({"net_name" : netName, "location" : location, "length": length, "layer": layer})
            except:
                print(netName, "has error.")

            SQS.append(data)

#存取df
dfsummary, dfSQS, dfSQSR = pd.DataFrame(summary), pd.DataFrame(SQS), pd.DataFrame(SQS)
print("step3: Transfer file format. -DONE")


#########################
###########################
############################

#step4: 分析txt
#修改df
print("step4: Parsing txt file...")
print("       Calculating... - 25%")
for i in netNameList:
    indexList = dfSQSR[dfSQSR["net_name"] == f"{i}"].index.tolist()
    
    # 填第一個元件的layer空格 
    # ex. TOP = TOP
    if len(indexList) > 1:
        dfSQSR.loc[indexList[0],"layer"] = dfSQSR.loc[indexList[1],"layer"]
    else:
        dfSQSR.loc[indexList[0],"layer"] = "TOP"
        
    #每個netname裡面找gap
    length = len(indexList)
    for index in indexList[::-1]:
        if length > 1:
            gap = dfSQSR.loc[index]["length"] - dfSQSR.loc[index-1]["length"]
            dfSQSR.loc[index,"gap"] = gap
        else:
            gap = 0
            dfSQSR.loc[index,"gap"] = gap
        length -= 1
print("       Calculating... - 50%")

#刪除多餘的VIA
deleteNullVIAROW(dfSQSR)  

#在summary建立branch path & branch length
for i in netNameList:
    indexList = dfSQSR[dfSQSR["net_name"] == f"{i}"].index.tolist()
    path = ""
    connIdxList = []
    MS = 0
    SL = 0
    NAN = 0
    
    for idx in indexList:
        ####################################################  前面的表層裡層    

        # try:
        #     if re.findall("BOTTOM|TOP", dfSQSR.loc[idx, "layer"]): 
        #         MS += dfSQSR.loc[idx, "gap"]

        #     elif re.findall("L\d+$|IN\d+$", dfSQSR.loc[idx, "layer"]):
        #         SL += dfSQSR.loc[idx, "gap"]

        #     else:
        #         NAN += dfSQSR.loc[idx, "gap"]
        # except:
        #     print(f"idx:{idx} is wrong.")
             

        ########################################################
        if not re.findall("VIA", dfSQSR.loc[idx, "location"]): #找出connnector index 排出VIA, VIA(T)
            connIdxList.append(idx)
    
    length = len(connIdxList)
    
    #找出connector 在每條indexlist 裡面的index
    num = 0
    netIndex = dfsummary[dfsummary["net_name"] == f"{i}"].index.tolist()
    
    #把起始點&終點 加入summary
    start_end = f"{dfSQSR.loc[indexList[0], 'location']}:{dfSQSR.loc[indexList[-1], 'location']}"
    dfsummary.loc[netIndex, "start_end_path"] = start_end
    
    ####################在這裡加入表層裡層
    # dfsummary.loc[netIndex, "path_MS"] = start_end + "-MS"
    # dfsummary.loc[netIndex, "length_MS"] = MS
    # dfsummary.loc[netIndex, "path_SL"] = start_end + "-SL"
    # dfsummary.loc[netIndex, "length_SL"] = SL
    
    
    for idx in range(length - 1):
        num +=1 
        pathIdx = []
        pathIdx.append(indexList.index(connIdxList[idx]))
        pathIdx.append(indexList.index(connIdxList[idx + 1]))
               
        #抓出兩兩conn
        connector = ""
        for j in pathIdx:
            connector += dfSQSR.loc[indexList[j], "location"] + ":"
        
        connector = connector[:-1] 
        dfsummary.loc[netIndex, f"path{num}"] = connector
        
        #算出兩兩conn間的長度
        branchLen = 0
        for k in indexList[ pathIdx[0]+1 : pathIdx[1]+1]:
            branchLen += dfSQSR.loc[k, "gap"]

        dfsummary.loc[netIndex, f"length{num}"] = branchLen
        
print("       Calculating... - 75%")

#調整dfsummary的順序
startEndColumn = dfsummary.pop(dfsummary.columns[2])
dfsummary.insert(1, startEndColumn.name, startEndColumn)
   
#轉成final SQS資料
column1 = []
column2 = []
for row in range(dfsummary.shape[0]):
    column1.append(dfsummary.loc[row,"net_name"])
    column1.append(dfsummary.loc[row,"start_end_path"])
    # column1.append(dfsummary.loc[row,"path_MS"])
    # column1.append(dfsummary.loc[row,"path_SL"])
    
    column2.append("")
    column2.append(dfsummary.loc[row,"total_length"])
    # column2.append(dfsummary.loc[row,"length_MS"])
    # column2.append(dfsummary.loc[row,"length_SL"])
    

    for num in range(branchPathNum(dfsummary)):

        column1.append(dfsummary.loc[row,f"path{num + 1}"])
        column2.append(dfsummary.loc[row,f"length{num + 1}"])
        
final = {
    "SQS"    : column1,
    "length" :column2
}
#轉成df 順便去掉空值
dfFinal = pd.DataFrame(final).dropna(axis=0)    
print("       Calculating... - 100%")
print("       Parse txt file. -DONE")    
    
# step5: 儲存檔案
filename = re.findall(r"^\w*", filepath)[0]
write = pd.ExcelWriter(f'{filename}.xlsx')

save_excel(write, dfFinal, "final")
save_excel(write, dfsummary, "summary")
save_excel(write, dfSQS, "data base")
save_excel(write, dfSQSR, "SQS")
write.save()

print(f"step5: Save data to {filename}.xlsx. -DONE")
