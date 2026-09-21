import re,unicodedata
def norm_text(s):
    s=unicodedata.normalize('NFC',s)
    s=s.replace('’',"'").replace('‘',"'").replace('–','-').replace('—','-').replace(' ',' ')
    s=re.sub(r'\s+',' ',s).strip()
    s=re.sub(r'\s*([(),;\-/])\s*',r'\1',s)
    s=re.sub(r'\.\s+','.',s)
    return s
