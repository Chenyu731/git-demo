# -*- coding: utf-8 -*-
# 用 template.html + data.json + app.js 組出 plant1.html
import os
B=os.path.dirname(os.path.abspath(__file__))+'/'
t=open(B+'template.html',encoding='utf-8').read()
d=open(B+'data.json',encoding='utf-8').read()
a=open(B+'app.js',encoding='utf-8').read()
t=t.replace('/*DATA*/',d).replace('/*APP*/',a)
open(B+'plant1.html','w',encoding='utf-8').write(t)
print(len(t))
