import re
import pandas as pd
import argparse

#讀入相關的參數
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--file", required=True, help="Path to the txt of the braod file.")
args = vars(ap.parse_args())



# 開啟檔案
def open_brd_file(filepath):
    f = open(filepath)
    return f

# parse net name
def parse_net_name(string):
    # 定義正規表達式
    netNameRex = re.compile(r"^\s-?[A-Z]+[0-9]*_?[A-Z]+[0-9]*.*")
    netName = netNameRex.findall(string)
    return netName

# 找到總長度的欄位
def total(string):
    # 定義正規表達式
    totalRex = re.compile("TOTAL")
    total = totalRex.findall(string)
    return total
#找到位置
def parse_net(string):
    # locationRex = re.compile(r"([U|R|C|L|J]\d+.[A-Z]*\d*|VIA\(T\)|VIA\s)")
    locationRex = re.compile(r"([U|R|C|L|J|T|P][A-Z]+\d+\.[A-Z]*\d*|[U|R|C|L|J|T|P][A-Z]+\.[A-Z]*\d*|[U|R|C|L|J|T|P|Q]\d+\.[A-Z]*\d*|[U|R|C|L|J|T|P][A-Z]*\d+\.[A-Z]*\d*|VIA\(T\)|VIA\s)")
    location = locationRex.findall(string)
    if location and location[0] == "VIA ":
        location[0] = location[0].replace(" ", "")
    return location

# #找到單一段長度
# def sub_length(string):
#     lengthRex = re.compile(r"(\d+.\d+)")
#     length = lengthRex.findall(string)[-1]
#     return length 

#找到單一段長度
def sub_length(string):
    lengthRex = re.compile(r"(\d+\.\d+)")
    length = lengthRex.findall(string)
    if length:
        length = length[-1]
    return length 

# 找到層數
def layer_num(string):
    layerRex = re.compile(r"BOTTOM|TOP|L\d+$")
    layer = layerRex.findall(string)
    return layer

#找到總長度
def total_length(string):
    ttlLength = re.findall(r"\d+.\d+", string)[0]
    return ttlLength

#存csv
def save_csv(datalist, filename):
    df = pd.DataFrame(datalist)
    df.to_csv(f'{filename}.csv', index = False)
    
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
    maxPathNum = int((df.shape[1] - 3) / 2)
    return maxPathNum



#step1: 開啟檔案
filepath = args["file"]
f = open_brd_file(filepath)
print(f"step1: {filepath} open.")

#step2: 解析檔案
SQS = []
summary = []
netNameList = []

for i in f:
    i = i.replace("\n","")#去掉換行符號
    #如果不是net name 也不是 total
    if not parse_net_name(i):
        if not parse_net(i):
            if not total(i):
                continue
            
    #如果是net name
    if parse_net_name(i):
        data = {} #清空
        netName = i.replace(" ", "")
        #建立netnamelist
        netNameList.append(netName)
        netPath = ""
#         data.update({"net_name" : netName})
#         SQS.append(data)
#         print(data)
    
    #如果是location
#     elif parse_net(i):
#         data = {} #清空

    elif parse_net(i):
        data = {} #清空            
        if sub_length(i):
            location = parse_net(i)[0]
            
            length = float(sub_length(i))
            layer = layer_num(i)[0] if layer_num(i) else ""
            data.update({"net_name" : netName, "location" : location, "length": length, "layer": layer})
            SQS.append(data)   
    
    #如果是total那一行
    elif total(i):
        data = {} #清空
        ttlLength = float(total_length(i))
        data.update({"net_name" : netName, "total_length" : ttlLength})
#         print(data)
        summary.append(data)
        
print(f"step2: {filepath} parsed done.")


#存取df
dfsummary, dfSQS, dfSQSR = pd.DataFrame(summary), pd.DataFrame(SQS), pd.DataFrame(SQS)

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
#         print(index, gap)

#刪除多餘的VIA
deleteNullVIAROW(dfSQSR)    
    
#在summary建立branch path & branch length
for i in netNameList:
    indexList = dfSQSR[dfSQSR["net_name"] == f"{i}"].index.tolist()
    path = ""
    connIdxList = []
    
    for idx in indexList:
        if not re.findall("VIA", dfSQSR.loc[idx, "location"]): #找出connnector index 排出VIA, VIA(T)
            connIdxList.append(idx)

    length = len(connIdxList)
    
    #找出connector 在每條indexlist 裡面的index
    num = 0
    netIndex = dfsummary[dfsummary["net_name"] == f"{i}"].index.tolist()
    
    #把起始點&終點 加入summary
    start_end = f"{dfSQSR.loc[indexList[0], 'location']}:{dfSQSR.loc[indexList[-1], 'location']}"
    dfsummary.loc[netIndex, "start_end_path"] = start_end

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

#調整dfsummary的順序
startEndColumn = dfsummary.pop(dfsummary.columns[2])
dfsummary.insert(1, startEndColumn.name, startEndColumn)  

#轉成final SQS資料
column1 = []
column2 = []
for row in range(dfsummary.shape[0]):
    column1.append(dfsummary.loc[row,"net_name"])
    column1.append(dfsummary.loc[row,"start_end_path"])
    column2.append("")
    column2.append(dfsummary.loc[row,"total_length"])


    for num in range(branchPathNum(dfsummary)):

        column1.append(dfsummary.loc[row,f"path{num + 1}"])
        column2.append(dfsummary.loc[row,f"length{num + 1}"])
        
final = {
    "SQS"    : column1,
    "length" :column2
}
#轉成df 順便去掉空值
dfFinal = pd.DataFrame(final).dropna(axis=0)  
   
# step3: 儲存檔案
filename = re.findall(r"^\w*", filepath)[0]
write = pd.ExcelWriter(f'{filename}.xlsx')
save_excel(write, dfFinal, "final")
write.save()

print(f"step3: {filename}.xlsx saved.")