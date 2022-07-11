# this file defines many functions for addressing text file
import re

def replace_line_in_text(file_name, old_str, new_str):
    file_data = ""
    with open (file_name, "r", encoding="utf-8") as f:
        for line in f:
            if old_str in line:
                line = line.replace(old_str,new_str)
            file_data += line
    with open(file_name,"w",encoding="utf-8") as f:
        f.write(file_data)

def replaceInPattern(file, key, newContent):
    with open (file, 'r+' ) as f:
        print("Writing in the field "+key+" to "+file+"")
        content = f.read()
        f.seek(0)
        f.write(re.sub(key, newContent, str(content), flags = re.M))
        f.truncate()
