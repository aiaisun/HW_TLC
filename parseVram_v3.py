import re
import pandas as pd
import argparse
from openpyxl import load_workbook
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

#刪除R開頭
def deleteRow3(string):
    pattern = re.compile(r"^R")
    delete = pattern.findall(string)
    return delete

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

# 存excel
def save_excel(write, df, sheetName):
#     df = pd.DataFrame(datalist)
    df.to_excel(write, sheet_name=f'{sheetName}', index=False)


##########################RUN CODE######################################
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
        try:
            location, length = i[0], float(i[-1])
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
        if not deleteRow3(i[0]):
            try:
                location, length, layer = i[0], float(i[-2]), i[-1]
                data.update({"net_name" : netName, "location" : location, "length": length, "layer": layer})
            except:
                print(netName, "has error.")

            SQS.append(data)

#存取df
dfsummary, dfSQS, dfSQSR = pd.DataFrame(summary), pd.DataFrame(SQS), pd.DataFrame(SQS)
print("step3: Transfer file format. -DONE")


# step3: 分析檔案 轉成sheet1 ans 2


#step4: 分析txt
#修改df
print("step4: Parsing txt file...")
print("       Calculating... - 25%")
#修改df
for i in netNameList:
    indexList = dfSQSR[dfSQSR["net_name"] == f"{i}"].index.tolist()
    
    # 填第一個元件的layer空格 
    # ex. TOP = TOP
    dfSQSR.loc[indexList[0],"layer"] = dfSQSR.loc[indexList[1],"layer"]
    
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
        if re.findall("BOTTOM|TOP", dfSQSR.loc[idx, "layer"]): 
            MS += dfSQSR.loc[idx, "gap"]
        elif re.findall("L\d+$|IN\d+$", dfSQSR.loc[idx, "layer"]):
            SL += dfSQSR.loc[idx, "gap"]
        else:
            NAN += dfSQSR.loc[idx, "gap"]
        
        ##########################################################
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
    dfsummary.loc[netIndex, "path_MS"] = start_end + "-MS"
    dfsummary.loc[netIndex, "length_MS"] = MS
    dfsummary.loc[netIndex, "path_SL"] = start_end + "-SL"
    dfsummary.loc[netIndex, "length_SL"] = SL
    
    
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

#表格2的columns
column3 = []
column4 = []
column5 = []

for row in range(dfsummary.shape[0]):
    column1.append(dfsummary.loc[row,"net_name"])
#     column1.append(dfsummary.loc[row,"start_end_path"])
    column1.append(dfsummary.loc[row,"path_MS"])
    column1.append(dfsummary.loc[row,"path_SL"])
    
    column2.append("")
#     column2.append(dfsummary.loc[row,"total_length"])
    column2.append(dfsummary.loc[row,"length_MS"])
    column2.append(dfsummary.loc[row,"length_SL"])
    
    #append到表格2的
    column3.append(dfsummary.loc[row,"net_name"])
    column3.append(dfsummary.loc[row,"net_name"])
    
    column4.append(dfsummary.loc[row,"path_MS"])
    column4.append(dfsummary.loc[row,"path_SL"])
    
    column5.append(dfsummary.loc[row,"length_MS"])
    column5.append(dfsummary.loc[row,"length_SL"])


    for num in range(branchPathNum(dfsummary)):

        column1.append(dfsummary.loc[row,f"path{num + 1}"])
        column2.append(dfsummary.loc[row,f"length{num + 1}"])
        
final = {
    "SQS"    : column1,
    "length" : column2
}

final2 = {
    "netname" : column3,
    "SQS"     : column4,
    "length"  : column5
}
#轉成df 順便去掉空值
dfFinal = pd.DataFrame(final).dropna(axis=0)        
dfFinal2 = pd.DataFrame(final2).dropna(axis=0)   

print("       Calculating... - 100%")
print("       Parse txt file. -DONE")
print("       Converted to sheet1 and sheet2. -DONE")
  

print("step5: Parsing txt file...")   
#step4: 做成sheet3
#轉成final SQS資料
sheet3column1 = []
sheet3column2 = []
sheet3column3 = []

for i in netNameList:
    indexList = dfSQSR[dfSQSR["net_name"] == f"{i}"].index.tolist()
#     u=0
    for idx in indexList:
        location = dfSQSR.loc[idx, "location"]

        
        if idx == dfSQSR.shape[0] -1 and re.findall("^U", location):
#             u+=1
            #因為是最後一個U, 找他上一個是不是VIA
            if re.findall("^V", dfSQSR.loc[idx - 1, "location"]):
                preLocation = dfSQSR.loc[idx - 1, "location"]

                #path
                path = f"{location}:{preLocation}"
                #gap已經算好 
                gap = dfSQSR.loc[idx, "length"] - dfSQSR.loc[idx-1, "length"]
                
                sheet3column1.append(i)
                sheet3column2.append(path)
                sheet3column3.append(gap)

                
            #如果上一個不是VIA, 再往前找一個VIA    
            elif re.findall("^V", dfSQSR.loc[idx - 2, "location"]):
                pre2Location = dfSQSR.loc[idx - 2, "location"]
                
                #path
                path = f"{location}:{pre2Location}"

                #前一個gap
                preGap = dfSQSR.loc[idx - 1, "length"] - dfSQSR.loc[idx - 2, "length"]
                
                #gap ( 2nd U - VIA - (1st U -VIA)  )
                gap = dfSQSR.loc[idx, "length"] - dfSQSR.loc[idx - 2, "length"] - preGap
                
                sheet3column1.append(i)
                sheet3column2.append(path)
                sheet3column3.append(gap)

            
            
        #如果找到U
        elif re.findall("^U", location):
#             u+=1
            #下一步看他下一個是不是VIA
            #如果是就是U:VIA 的距離
            if re.findall("^V", dfSQSR.loc[idx+1, "location"]):
                nextLocation = dfSQSR.loc[idx+1, "location"]
                
                #path
                path = f"{location}:{nextLocation}"
                #gap
                gap = dfSQSR.loc[idx+1, "length"] - dfSQSR.loc[idx, "length"]
                
                sheet3column1.append(i)
                sheet3column2.append(path)
                sheet3column3.append(gap)

            
            #如果下一個不是VIA, 找他上一個是不是VIA
            elif re.findall("^V", dfSQSR.loc[idx - 1, "location"]):
                preLocation = dfSQSR.loc[idx - 1, "location"]

                #path
                path = f"{location}:{preLocation}"
                
                #gap已經算好 
                gap = dfSQSR.loc[idx, "length"] - dfSQSR.loc[idx-1, "length"]
                
                sheet3column1.append(i)
                sheet3column2.append(path)
                sheet3column3.append(gap)

                
            #如果下一個不是VIA, 上一個不是VIA, 再往前找一個    
            elif re.findall("^V", dfSQSR.loc[idx - 2, "location"]):
                pre2Location = dfSQSR.loc[idx - 2, "location"]
                
                #path
                path = f"{location}:{pre2Location}"
                #前一個gap
                preGap = dfSQSR.loc[idx - 1, "length"] - dfSQSR.loc[idx - 2, "length"]
                
                #gap ( 2nd U - VIA - (1st U -VIA)  )
                gap = dfSQSR.loc[idx, "length"] - dfSQSR.loc[idx - 2, "length"] - preGap
                 
                sheet3column1.append(i)
                sheet3column2.append(path)
                sheet3column3.append(gap)

                
            else:
                print("not found")
#         else:
#             print("False")
   
    
final3 = {
    "netname"  : sheet3column1,
    "path"     : sheet3column2,
    "length"   : sheet3column3
}

dfFinal3 = pd.DataFrame(final3).dropna(axis=0) 
    
print("       Converted to sheet3. -DONE")   
    
# step5: 儲存檔案
filename = re.findall(r"^\w*", filepath)[0]
write = pd.ExcelWriter(f'{filename}.xlsx')
save_excel(write, dfFinal, "final")
save_excel(write, dfFinal2, "final2")
save_excel(write, dfFinal3, "final3")
# save_excel(write, dfsummary, "summary")
# save_excel(write, dfSQS, "data base")
# save_excel(write, dfSQSR, "SQS")
write.save()

print(f"step6: Save data to {filename}.xlsx. -DONE")  