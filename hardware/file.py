import os

def file_exists(file_path):
    directory = '/' if '/' not in file_path else file_path.rsplit('/', 1)[0]
    files = os.listdir(directory)
    file_name = file_path.split('/')[-1]
    return file_name in files

def openFile(count=1):
    file_path = f"test-{count}.csv"
    if file_exists(file_path):
        return openFile(count+1)
    else:
        return open(file_path, "w")
