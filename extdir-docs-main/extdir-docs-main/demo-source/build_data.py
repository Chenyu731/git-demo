# -*- coding: utf-8 -*-
import re, json, collections, openpyxl
import os
S=os.path.dirname(os.path.abspath(__file__))+'/'
wb=openpyxl.load_workbook(S+'一廠分機表.xlsx'); ws=wb.active
grade={}; chart_ext=set()
for r in range(3,55):
    for a,b in ((2,3),(5,6),(8,9)):
        e=ws.cell(r,a).value; g=ws.cell(r,b).value
        if isinstance(e,int):
            chart_ext.add(e)
            if g: grade[e]=g
# key, name, parent, fill, col(top-level only), default ext, range
D=[
('gm','總經理室',None,None,1,None,'100-109'),
('fz','廠長室',None,None,1,None,'100-109'),
('sg','生管課','fz',None,0,None,'104-106'),
('hr','人事室',None,None,1,None,'110-119'),
('p1','生產一部',None,None,1,None,'200-209'),
('h1','合一課','p1',None,0,None,'210-219'),
('z1','製一組','h1',None,0,211,None),
('z2','製二組','h1',None,0,211,None),
('h2','合二課','p1',None,0,None,'220-229'),
('z3','製三組','h2',None,0,221,None),
('z4','製四組','h2',None,0,221,None),
('h3','合三課','p1',None,0,240,'240-249'),
('z7','製七組','h3',None,0,241,None),
('sb','S棟','h3',None,0,242,None),
('p3','生產三部',None,None,1,None,'200-209'),
('h4','合四課','p3',None,0,None,'250-259'),
('z8','製八組','h4',None,0,251,None),
('lb','L棟無塵室','h4',None,0,252,None),
('al','ALPHA ROOM','h4',None,0,253,None),
('lab','實驗工場',None,None,1,None,'260-269'),
('hs','安全衛生室',None,None,1,None,'400-499'),
('p2','生產二部',None,None,2,None,'500-599'),
('s1','噴乾一課','p2',None,0,511,'510-519'),
('lq','液品課','p2',None,0,None,'530-539'),
('cp','成品課','p2',None,0,541,'540-549'),
('gz','乾燥課','p2',None,0,541,'540-549'),
('jx','精細課','p2',None,0,550,'550-559'),
('qa','品保部',None,None,2,None,'300-399'),
('q1','品一課','qa',None,0,311,'310-319'),
('q2','品二課','qa',None,0,323,'320-329'),
('jy','技銷處',None,None,2,None,'150-189'),
('w5','技銷處五部','jy','y',0,None,'150-189'),
('mt','金技課','w5','c',0,161,'160-169'),
('lt','皮技課','w5',None,0,170,'170-179'),
('pp','紙技課','w5',None,0,180,'180-189'),
('ep','環保部',None,None,2,None,'700-799'),
('e1','環保課','ep',None,0,710,'710-719'),
('e2','環資課','ep',None,0,720,'720-729'),
('fw','廠務部',None,None,3,None,'600-699'),
('zw','總務課','fw',None,0,None,'610-619'),
('rm','原料課','fw',None,0,622,'620-629'),
('hz','環資管理處',None,None,3,None,'800-899'),
('wm','工程管理暨智慧製造處',None,None,3,None,'900-999'),
('m1','工智處一部一課','wm','c',0,910,'910-919'),
('m2','工智處工程管理部','wm','c',0,None,'900-909'),
('m3','工智處智慧製造部','wm','c',0,None,'930-939'),
]
R=[]
def P(d,n,t,e): R.append(dict(t='P',d=d,n=n,title=t,ext=e,personal=True))
def U(d,n,e,note=''): R.append(dict(t='U',d=d,n=n,pn=n,ext=e,note=note))
U(None,'緊急專線',119); U(None,'總機',613); P(None,'陳坤木','廠長',101); P(None,'陳勳振','副廠長',103)
P('gm','康源昇','特助',120); P('gm','廖嘉鍾','特助',102)
P('fz','李靜安','技術經理',108); P('fz','楊馥瑄','',105); P('fz','李欣庭','',109); P('fz','黃明傑','',107)
P('sg','梁冬梅','副理',104); P('sg','吳家綺','',106)
P('hr','邱曉芳','副理',110); U('hr','守衛室',111); P('hr','吳靜怡','',112); P('hr','賴升美','',113)
P('p1','楊育峰','經理',201); P('p1','孫立平','副理',202)
P('h1','黃俊華','課長',210); U('z1','製一組',211); U('z2','製二組',211)
P('h2','余政峰','課長',220); U('z3','製三組',221); U('z4','製四組',221)
U('h3','合三課',240); U('z7','製七組',241); U('sb','S棟',242)
P('p3','陳柏瑀','經理',203); P('p3','王凱民','副理',204)
P('h4','温啟銘','課長',250); U('z8','製八組',251); U('lb','L棟無塵室',252); U('al','ALPHA ROOM',253)
U('lab','實驗工場',260); U('lab','實驗室',261); U('lab','連續製程辦公室',262); U('lab','連續製程辦公室',263)
P('hs','許峰睿','副主任',402); P('hs','張惠鎔','',403); P('hs','余國馳','',404)
P('p2','林忠鵬','經理',501); P('p2','周致豪','副理',503)
P('s1','劉任偉','課長',510); U('s1','噴一課 (A棟)',511); U('s1','噴一課 (M棟)',512)
P('lq','陳柏蒼','副課長',530)
P('cp','陳文濬','課長',540); U('cp','成品課 (H棟)',541); U('cp','成品課 (J棟)',542)
U('gz','乾燥課 (H棟)',541); U('gz','乾燥課 (J棟)',542)
U('jx','精細課',550); U('jx','六樓',551)
P('qa','楊賀鈞','經理',301)
P('q1','林鈺偉','副理',302); U('q1','品一課 (2F)',311); U('q1','品一課 (4F)',312)
P('q2','陳文斌','課長',320); U('q2','品二課 (X棟儀器室)',323); U('q2','應用組 (L棟)',321); U('q2','應用組實驗室',322)
P('jy','王殷光','處長',150)
P('w5','賴致中','經理',151); P('w5','王乃慶','副理',152)
P('mt','江富誠','課長',160); U('mt','金技課',161)
U('lt','皮技課',170); U('lt','皮技課',171)
U('pp','紙技課',180)
P('ep','陳啟華','經理',701); U('e1','環保課',710); U('e2','環資課',720)
P('fw','蘇聰賢','經理',601)
P('zw','陳秋宏','課長',610); P('zw','黃傑','組長',612); P('zw','張淑如','',611); P('zw','余明柔','',613)
U('zw','e-learning',615); U('zw','外勞宿舍',616); U('zw','餐廳',617); U('zw','2、3樓機房',619); U('zw','行動辦公室',620); U('zw','會客室',640); U('zw','禮堂',698); U('zw','第三會議室',699)
P('rm','林品郡','組長',621); U('rm','原料課',622)
P('hz','林礽龍','處長',801)
for n,e in (('林日珅',811),('鍾詠丞',812),('蔡宜蓁',813),('胡忠仁',814)): P('hz',n,'',e)
P('wm','黃樹瑆','副處長',901)
P('m1','蔡道明','副理',902); U('m1','工智處一課',910)
P('m2','穆彥池','副理',903)
for n,e in (('李奕承',922),('康睜芳',923),('李安炖',925)): P('m2',n,'',e)
P('m3','劉子瑜','組長',931); P('m3','李鎮宇','',932); P('m3','董怡宣','',933); P('m3','楊梓盛','',924)
for i,r in enumerate(R): r['sort']=i+1
EMPTY={614:'zw',815:'hz',816:'hz',817:'hz',818:'hz',819:'hz'}
used={r['ext'] for r in R}
print('chart ext count',len(chart_ext),'diff vs records+empty:',sorted((used|set(EMPTY))^chart_ext))
old=open(S+'old-eip-plant1.html',encoding='utf-8').read()
rows=re.findall(r"\{plant:'一廠',dept:\"([^\"]*)\",name:\"([^\"]*)\",title:\"([^\"]*)\",ext:\"([^\"]*)\",type:'([^']*)',ab:'([^']*)'\}",old)
MAP={'生產一部 › 合一課 › 製一組':'z1','生產一部 › 合一課 › 製二組':'z2','生產一部 › 合二課 › 製三組':'z3','生產一部 › 合二課 › 製四組':'z4',
'生產一部 › 合三課 › 製七組':'z7','生產一部 › 合三課':'h3','生產二部 › 噴一課':'s1','生產二部 › 液品課':'lq','生產二部 › 精細課':'jx','生產二部 › 成品課':'cp','生產二部 › 成品課 › 乾燥組':'gz',
'生產三部 › 合四課 › 製八組':'z8','實驗工場':'lab','環保部 › 環保課':'e1','環保部 › 環資課':'e2','品保部 › 品一課':'q1','品保部 › 品二課':'q2','品保部 › 品二課 › 應用組':'q2',
'技銷處五部 › 金技課':'mt','技銷處五部 › 皮技課':'lt','技銷處五部 › 紙技課':'pp','工程管理暨智慧製造處 › 一部一課':'m1','工程管理暨智慧製造處 › 工程管理部':'m2','工程管理暨智慧製造處 › 智慧製造部':'m3',
'環資管理處 › 永續資源組':'hz','環資管理處 › 環境資訊組':'hz','環資管理處 › 環保技術組':'hz','廠務部 › 總務課':'zw','廠務部 › 原料課':'rm'}
listed={r['n'] for r in R if r['t']=='P'}
shared=[]; skipped=collections.Counter()
for dpt,n,t,e,ty,ab in rows:
    if ty!='人員' or n in listed: continue
    k=MAP.get(dpt)
    if not k: skipped[dpt]+=1; continue
    if t: skipped['has title:'+dpt]+=1; continue
    shared.append(dict(t='P',d=k,n=n,title='',ext=int(e),personal=False))
for i,s in enumerate(shared): s['sort']=1000+i
unit_ext=collections.defaultdict(set)
for r in R:
    if r['t']=='U' and r['d']: unit_ext[r['d']].add(r['ext'])
bad=[(s['d'],s['n'],s['ext']) for s in shared if s['ext'] not in unit_ext.get(s['d'],set())]
print('shared staff',len(shared),'| listed persons',len(listed),'| skipped',dict(skipped))
print('shared whose old ext is not a unit ext of their dept:',len(bad),bad[:20])
json.dump(dict(D=D,R=R,SH=shared,GR={str(k):v for k,v in grade.items()},EMPTY={str(k):v for k,v in EMPTY.items()}),
          open(S+'data.json','w',encoding='utf-8'),ensure_ascii=False)
