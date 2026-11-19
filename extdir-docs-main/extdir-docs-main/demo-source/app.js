(function(){
var $=function(id){return document.getElementById(id)};
var esc=function(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})};
var TODAY='2026-11-08';
// 分機數字：每個數字固定寬度，不受字型影響（有些字型的 1 比較窄，數字會對不齊）
function nd(n){return String(n).split('').map(function(c){return '<span class="nd">'+c+'</span>'}).join('')}

/* ================= 資料 ================= */
var depts=DATA.D.map(function(d,i){return {id:d[0],name:d[1],parent:d[2],fill:d[3],col:d[4]||0,def:d[5],range:d[6],sort:i,active:true,hdr:true}});
['z1','z2','z3','z4','z7','z8','sb','lb','al'].forEach(function(k){dById(k).hdr=false});
function dById(id){for(var i=0;i<depts.length;i++)if(depts[i].id===id)return depts[i];return null}
var ordCnt={};depts.forEach(function(d){if(d.col){ordCnt[d.col]=(ordCnt[d.col]||0)+1;d.ord=ordCnt[d.col]}});
var nid=0;
var recs=[];
DATA.R.forEach(function(r){recs.push({id:++nid,t:r.t,name:r.n,pn:r.pn||'',dept:r.d,title:r.title||'',ext:r.ext,personal:!!r.personal,inDir:true,hide:false,active:true,sort:r.sort,note:r.note||'',email:'e'+(1000+nid)+'@ecic.com.tw'})});
DATA.SH.forEach(function(r){
  var d=dById(r.d);var e=(d&&d.def)?d.def:r.ext;
  if(r.n==='六樓')return;
  recs.push({id:++nid,t:'P',name:r.n,pn:'',dept:r.d,title:'',ext:e,personal:false,inDir:true,hide:false,active:true,sort:r.sort,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'});
});
var GRADE={};Object.keys(DATA.GR).forEach(function(k){GRADE[k]=DATA.GR[k]});
var exts=[];var seenE={};
function ownerOf(e){
  if(e===613)return 'zw';
  var u=recs.filter(function(r){return r.ext===e&&r.dept&&r.t==='U'})[0];if(u)return u.dept;
  var p=recs.filter(function(r){return r.ext===e&&r.dept})[0];if(p)return p.dept;
  return DATA.EMPTY[String(e)]||null;
}
recs.forEach(function(r){if(!seenE[r.ext]){seenE[r.ext]=1;exts.push({ext:r.ext,dept:ownerOf(r.ext),grade:GRADE[r.ext]||'',note:''})}});
Object.keys(DATA.EMPTY).forEach(function(k){var e=+k;if(!seenE[e]){seenE[e]=1;exts.push({ext:e,dept:DATA.EMPTY[k],grade:GRADE[e]||'',note:'空號'})}});
exts.sort(function(a,b){return a.ext-b.ext});
var PLANT={name:'一廠',foot:['專線: 公司#80   一廠#81   二廠#82   三廠#83   四廠#84  聽到忙線音後直撥分機號碼，由總機小姐接聽，代轉分機。','台北公司:TEL(02)2706-6006   FAX(02)2708-1254','永光一廠:TEL(03)386-8081　 FAX(03)386-8048','永光二廠:TEL(03)483-8088　 FAX(03)483-8008　　中部辦事處:TEL(04)2358-3378   FAX(04)2358-2378','永光三廠:TEL(03)483-7682　 FAX(03)483-7683　　南部辦事處:TEL(06)215-2589　 FAX(06)215-3639','永光四廠:TEL(03)473-7366　 FAX(03)473-7909','上海明德專線：工廠撥打上海明德，先按#80，再按888，等響鈴聲結束後，再按66，由總機小姐接聽，代轉分機。']};
var LOG=[];var changed=3;
function log(who,what){LOG.unshift({t:TODAY+' '+('0'+(new Date().getHours())).slice(-2)+':'+('0'+(new Date().getMinutes())).slice(-2),who:who,what:what})}
var seedLog=[['系統','自動處理：新進 林小華（範例）加入「製三組」，使用公用分機 221'],['系統','自動處理：離職 陳小強（範例）停用，原用公用分機 211'],['系統','自動處理：調部門 黃小美（範例）「品一課」→「品二課」，分機改為 323'],['系統','Email 為 f＋數字的 2 位新進，已設為「不列入分機表」，未通知'],['廠務（範例）','修改分機號碼表：614 備註「空號」']];
seedLog.slice().reverse().forEach(function(x){LOG.unshift({t:'2026-11-07 08:0'+LOG.length,who:x[0],what:x[1]})});
function touch(who,what){log(who||'廠務（範例）',what);changed++}

/* ================= 部門工具 ================= */
function kids(pid){return depts.filter(function(d){return d.parent===pid&&d.active}).sort(function(a,b){return a.sort-b.sort})}
function tops(){return depts.filter(function(d){return !d.parent&&d.active}).sort(function(a,b){return a.sort-b.sort})}
function flat(){var out=[];(function walk(pid,lv){(pid===null?tops():kids(pid)).forEach(function(d){out.push({d:d,lv:lv});walk(d.id,lv+1)})})(null,0);return out}
function path(id){if(!id)return '（置頂・無部門）';var a=[],d=dById(id);while(d){a.unshift(d.name);d=d.parent?dById(d.parent):null}return a.join(' › ')}
function short(id){if(!id)return '（置頂）';var d=dById(id);return d.parent?dById(d.parent).name+' › '+d.name:d.name}
function topOf(id){var d=dById(id);while(d&&d.parent)d=dById(d.parent);return d}
function inTree(id,root){var d=dById(id);while(d){if(d.id===root)return true;d=d.parent?dById(d.parent):null}return false}
function deptOpts(sel,withNone){var h=withNone?'<option value="">（置頂・無部門）</option>':'';flat().forEach(function(x){h+='<option value="'+x.d.id+'"'+(x.d.id===sel?' selected':'')+'>'+'　'.repeat(x.lv)+esc(x.d.name)+'</option>'});return h}
function spaced(n){return n.length<=5?n.split('').join('　'):n}
var MGR=['課長','副理','經理','處長','副處長','廠長','副廠長','技術經理','副主任'];
function isMgr(t){return MGR.indexOf(t)>-1}
function gradeOf(e){var x=extOf(e);return x?x.grade:''}
function extOf(e){for(var i=0;i<exts.length;i++)if(exts[i].ext===e)return exts[i];return null}
function users(e){return recs.filter(function(r){return r.active&&r.ext===e})}
function inRange(e,rg){if(!rg)return true;var m=rg.split('-');return e>=+m[0]&&e<=+m[1]}
function titleRank(t){var o=['廠長','副廠長','處長','副處長','部長','經理','技術經理','副理','課長','副課長','副主任','組長'];var i=o.indexOf(t);return i<0?99:i}

/* ================= 導覽 ================= */
var VIEWS=[['search','查詢'],['inbox','異動收件匣'],['edit','人員與單位'],['dept','部門表'],['ext','分機號碼表'],['layout','列印版面'],['export','匯出'],['log','異動紀錄']];
var view='search';
function go(v,arg){if(v==='p2'){v='layout';arg={tab:2}}view=v;if(arg)goArg=arg;render()}
var goArg=null;
function renderNav(){
  var h='';VIEWS.forEach(function(x){var on=x[0]===view;h+='<button role="tab" aria-selected="'+on+'" class="'+(on?'on':'')+'" data-v="'+x[0]+'">'+x[1]+(x[0]==='inbox'&&pendingN()?'<span class="cnt">'+pendingN()+'</span>':'')+'</button>'});
  $('nav').innerHTML=h;
  Array.prototype.forEach.call($('nav').children,function(b){b.onclick=function(){go(b.getAttribute('data-v'))}});
}
function toast(t){var e=$('toast');e.textContent=t;e.classList.remove('hide');clearTimeout(toast.h);toast.h=setTimeout(function(){e.classList.add('hide')},3200)}

/* ================= 異動收件匣資料 ================= */
var INBOX=[
 {id:'a1',kind:'auto',tag:'new',label:'新進',who:'林小華（範例）',det:'Domino 部門「製三組」對得上、非主管、部門預設分機 221 → 已加入，使用公用分機 221。',done:false,rid:null},
 {id:'a2',kind:'auto',tag:'out',label:'離職',who:'陳小強（範例）',det:'原使用「製一組」公用分機 211 → 已停用（不刪除）。',done:false,rid:null},
 {id:'a3',kind:'auto',tag:'mv',label:'調部門',who:'黃小美（範例）',det:'「品一課」→「品二課」，新部門預設分機 323 → 分機由 311 改為 323。',done:false,rid:null},
 {id:'p1',kind:'pend',tag:'new',label:'新進・主管',who:'周大成（範例）',det:'Domino 部門「環資管理處」，職稱「副理」。主管需要個人分機，系統列出該部門空號供挑選。',btn:'新增並選分機',act:'newMgr'},
 {id:'p2',kind:'pend',tag:'mv',label:'部門對不上',who:'資訊管理課（1 位新進）',det:'Domino 出現部門名稱「資訊管理課」，部門表裡沒有對應。請指定放在哪個既有部門，或新增為部門（在部門表新增同名部門也會自動對應）。處理完之後，這位新進（吳小芬）會再產生一筆「補分機」的待確認。',btn:'到部門表處理',act:'mapDept'},
 {id:'p3',kind:'pend',tag:'out',label:'離職・有個人分機',who:'蔡小宇（範例）',det:'環資管理處，個人分機 815。貼牆表會少一列，分機可能交接。確認後 815 回到環資管理處的空號。',btn:'確認停用',act:'confirmOut'},
 {id:'p4',kind:'pend',tag:'up',label:'原地升遷',who:'謝小春（範例）',det:'乾燥課，職稱「組長」→「課長」，但沒有個人分機。',btn:'新增個人分機',act:'newMgr2'},
 {id:'p5',kind:'pend',tag:'mv',label:'可能是部門改名',who:'9 人',det:'9 人同時從「品一課」換到「品質一課」。請到部門表改名後整批套用，不要逐人處理。',btn:'改名並整批套用',act:'renameBatch'}
];
function pendingN(){return INBOX.filter(function(x){return x.kind==='pend'&&!x.done}).length}
// 已自動處理的三筆：實際加到資料裡，才能示範「還原」
(function(){
  var r1={id:++nid,t:'P',name:'林小華（範例）',pn:'',dept:'z3',title:'',ext:221,personal:false,inDir:true,hide:false,active:true,sort:2000,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'};recs.push(r1);INBOX[0].rid=r1.id;
  var r2={id:++nid,t:'P',name:'陳小強（範例）',pn:'',dept:'z1',title:'',ext:211,personal:false,inDir:true,hide:false,active:false,sort:2001,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'};recs.push(r2);INBOX[1].rid=r2.id;
  var r4={id:++nid,t:'P',name:'蔡小宇（範例）',pn:'',dept:'hz',title:'',ext:815,personal:true,inDir:true,hide:false,active:true,sort:2003,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'};recs.push(r4);INBOX.filter(function(i){return i.id==='p3'})[0].rid=r4.id;
  var r5={id:++nid,t:'P',name:'謝小春（範例）',pn:'',dept:'gz',title:'組長',ext:541,personal:false,inDir:true,hide:false,active:true,sort:2004,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'};recs.push(r5);INBOX.filter(function(i){return i.id==='p4'})[0].rid=r5.id;
  var r3={id:++nid,t:'P',name:'黃小美（範例）',pn:'',dept:'q2',title:'',ext:323,personal:false,inDir:true,hide:false,active:true,sort:2002,note:'',email:'e'+(1000+nid)+'@ecic.com.tw'};recs.push(r3);INBOX[2].rid=r3.id;
})();
function rById(id){for(var i=0;i<recs.length;i++)if(recs[i].id===id)return recs[i];return null}
var inboxDone=[];
function closeInbox(id,detail){var it=INBOX.filter(function(i){return i.id===id})[0];if(!it||it.done)return;it.done=true;inboxDone.push('已處理：'+it.label+' '+it.who+(detail?'，'+detail:''));log('廠務（範例）','處理異動：'+it.label+' '+it.who+(detail?'（'+detail+'）':''))}
function topSort(dept){var m=null;recs.forEach(function(r){if(r.dept===dept&&(m===null||r.sort<m))m=r.sort});return (m===null?0:m)-1}

/* ================= 列印版面（貼牆版）建構 ================= */
function printable(r){return r.active&&r.inDir&&!r.hide&&(r.t==='U'||r.personal)}
function itemsOf(d){
  var id=d?d.id:null,own=recs.filter(function(r){return printable(r)&&r.dept===id});
  // 空號也印一列（名稱留空），位置接在所屬部門內前一支分機後面
  exts.filter(function(x){return x.dept===id&&id&&users(x.ext).length===0}).forEach(function(x){
    var prev=own.filter(function(r){return r.t!=='E'&&r.ext<x.ext}).sort(function(a,b){return b.ext-a.ext})[0];
    own.push({t:'E',ext:x.ext,sort:(prev?prev.sort:0)+0.5+x.ext/100000,name:''});
  });
  return own.sort(function(a,b){return a.sort-b.sort})}
function rowOfRec(r){if(r.t==='E')return {k:'e',text:'',ext:r.ext,rec:r};return r.t==='U'?{k:'u',text:r.pn||r.name,ext:r.ext,rec:r}:{k:'p',text:r.name+(r.title?'  '+r.title:''),ext:r.ext,rec:r}}
function blockRows(d,lv){
  var rows=[];
  var own=itemsOf(d),ch=kids(d.id);
  var showHead=d.hdr!==false||ch.length||own.some(function(r){return r.t==='P'});
  if(showHead)rows.push({k:lv===0?'h1':'h2',text:lv===0?spaced(d.name):d.name,fill:d.fill,dept:d.id});
  own.forEach(function(r){rows.push(rowOfRec(r))});
  ch.forEach(function(c){blockRows(c,lv+1).forEach(function(x){rows.push(x)})});
  return rows;
}
function dedupe(rows){ // 相鄰相同分機只印第一次
  var prev=null;rows.forEach(function(r){if(r.ext!=null){r.blank=(prev===r.ext);prev=r.ext}else prev=null});
  return rows;
}
function layout(){
  var cols=[[],[],[]],lens=[0,0,0];
  var top=itemsOf(null).map(rowOfRec);
  var blocks=tops().slice().sort(function(a,b){return (a.col||9)-(b.col||9)||(a.ord||0)-(b.ord||0)});
  var res={cols:[[],[],[]],blocks:[]};
  if(top.length)res.cols[0].push({rows:dedupe(top),dept:null});
  blocks.forEach(function(d){var rows=dedupe(blockRows(d,0));var c=d.col>=1&&d.col<=3?d.col-1:null;res.blocks.push({d:d,rows:rows,col:c});if(c!==null)res.cols[c].push({rows:rows,dept:d})});
  res.counts=res.cols.map(function(c){return c.reduce(function(s,b){return s+b.rows.length},0)});
  return res;
}
function fmtDate(){return '2026年11月08日'}
function rowsHtml(rows){
  var h='',i=0;
  while(i<rows.length){
    var r=rows[i];
    if(r.k==='h1'){h+='<div class="r h1">'+esc(r.text)+'</div>';i++;continue}
    if(r.k==='h2'){h+='<div class="r h2 '+(r.fill||'')+'">'+esc(r.text)+'</div>';i++;continue}
    var j=i+1;while(j<rows.length&&rows[j].blank)j++;var n=j-i;
    if(n===1){h+='<div class="r"><div>'+esc(r.text)+'</div><div>'+r.ext+'</div><div>'+esc(gradeOf(r.ext))+'</div></div>';i++;continue}
    // 相鄰的列用同一支分機：分機欄合併成一格（和貼牆表的合併儲存格一樣）
    h+='<div class="r m" style="grid-template-rows:repeat('+n+',17px)">';
    for(var k=i;k<j;k++){var last=k===j-1,bb=last?'':'border-bottom:1px solid #000;';
      h+='<div style="grid-column:1;grid-row:'+(k-i+1)+';'+bb+'">'+esc(rows[k].text)+'</div><div style="grid-column:3;grid-row:'+(k-i+1)+';'+bb+'">'+esc(gradeOf(rows[k].ext))+'</div>'}
    h+='<div class="mx" style="grid-column:2;grid-row:1 / span '+n+'">'+r.ext+'</div></div>';
    i=j;
  }
  return h;
}
function sheet1(){
  var L=layout(),h='<div class="sheet portrait p1"><div class="tt">'+esc(PLANT.name)+'各單位分機號碼表<small>修訂日期：'+fmtDate()+'</small></div><div class="grid">';
  L.cols.forEach(function(c){h+='<div class="col">';c.forEach(function(b){h+=rowsHtml(b.rows)});h+='</div>'});
  h+='</div><div class="foot">'+PLANT.foot.map(function(x){return '<div>'+esc(x)+'</div>'}).join('')+'</div></div>';
  return h;
}
function checks(){
  var out=[],L=layout();
  recs.filter(function(r){return r.active&&r.t==='P'&&isMgr(r.title)&&!r.personal}).forEach(function(r){out.push({lv:'w',t:'課長以上沒有個人分機：'+r.name+'（'+r.title+'，'+short(r.dept)+'）'})});
  var seenD={};recs.filter(function(r){return r.active&&r.inDir&&r.t==='P'&&!r.personal&&r.dept}).forEach(function(r){
    var has=recs.some(function(u){return u.active&&u.t==='U'&&u.dept===r.dept&&u.ext===r.ext});var k=r.dept+'|'+r.ext;
    if(!has&&!seenD[k]){seenD[k]=1;out.push({lv:'w',t:'「'+short(r.dept)+'」有人使用公用分機 '+r.ext+'，但該部門沒有單位紀錄，貼牆表印不出來'})}});
  var byExt={};recs.filter(printable).forEach(function(r){(byExt[r.ext]=byExt[r.ext]||[]).push(r)});
  Object.keys(byExt).forEach(function(e){var ds={};byExt[e].forEach(function(r){ds[r.dept||'_']=1});if(Object.keys(ds).length>1)out.push({lv:'w',t:'分機 '+e+' 出現在不同部門（'+Object.keys(ds).map(function(k){return k==='_'?'置頂':short(k)}).join('、')+'），而且都沒標「不列」'})});
  tops().forEach(function(d){if(!(d.col>=1&&d.col<=3))out.push({lv:'w',t:'「'+d.name+'」沒有指定欄'})});
  L.counts.forEach(function(n,i){if(n>52)out.push({lv:'w',t:'第 '+(i+1)+' 欄有 '+n+' 列，超過約 52 列'})});
  return out;
}

/* ================= 頁面：查詢 ================= */
var sQ='',sMode='list',sTop='';
function vSearch(){
  var h='<section class="wrap"><div><h1>找分機</h1><div class="sub">輸入姓名、部門或分機號碼；也可以搜尋會議室、守衛室等單位。</div><div class="muted" style="margin-top:6px">你的權限：一廠廠務。姓名旁的 ✎ 點下去直接編輯。其他廠區只能查詢（第二階段）。</div></div>'+
  '<input class="in" style="max-width:560px;height:46px" type="search" id="q" value="'+esc(sQ)+'" placeholder="例如：品保、守衛室、211、陳文斌" aria-label="搜尋">'+
  '<div style="display:flex;flex-wrap:wrap;gap:12px 24px;justify-content:space-between"><div class="chips" id="tops"></div><div class="chips"><button class="chip'+(sMode==='list'?' on':'')+'" data-m="list">清單</button><button class="chip'+(sMode==='card'?' on':'')+'" data-m="card">分機表</button></div></div>'+
  '<div id="sres"></div><div class="muted">資料由廠務維護，最後更新：'+TODAY+'。撥打方式：先按廠別代碼（一廠 #81），聽到忙線音後直撥分機。</div></section>';
  return h;
}
function sHit(r){
  if(!r.active||!r.inDir)return false;
  if(sTop&&!(r.dept&&inTree(r.dept,sTop)))return false;
  var k=sQ.trim().toLowerCase();if(!k)return true;
  return [r.name,r.pn,r.title,String(r.ext),path(r.dept)].some(function(s){return String(s).toLowerCase().indexOf(k)>-1});
}
function drawSearch(){
  var t='<button class="chip'+(sTop===''?' on':'')+'" data-t="">全部</button>';tops().forEach(function(d){t+='<button class="chip'+(sTop===d.id?' on':'')+'" data-t="'+d.id+'">'+esc(d.name)+'</button>'});
  $('tops').innerHTML=t;Array.prototype.forEach.call($('tops').children,function(b){b.onclick=function(){sTop=b.getAttribute('data-t');drawSearch()}});
  var rs=recs.filter(sHit),h='';
  if(sMode==='list'){
    h='<div class="box scroll"><div style="min-width:720px"><div class="row head" style="grid-template-columns:1.3fr 1.6fr 1fr 80px 70px"><div>姓名／單位</div><div>部門</div><div>職稱</div><div>分機</div><div>等級</div></div>';
    rs.sort(function(a,b){return a.ext-b.ext});
    rs.slice(0,80).forEach(function(r){h+='<div class="row" style="grid-template-columns:1.3fr 1.6fr 1fr 80px 70px"><div><button class="who" data-ed="'+r.id+'" aria-label="編輯 '+esc(r.name)+'">'+esc(r.name)+' ✎</button> '+(r.t==='U'?'<span class="badge u">單位</span>':'')+'</div><div>'+esc(short(r.dept))+'</div><div>'+esc(r.title)+'</div><div class="ext">'+r.ext+'</div><div>'+esc(gradeOf(r.ext))+'</div></div>'});
    if(!rs.length)h+='<div class="row">沒有符合的結果</div>';
    h+='</div></div><div class="muted">'+(rs.length>80?'顯示前 80 筆，共 '+rs.length+' 筆。':'共 '+rs.length+' 筆。')+'</div>';
  }else{
    h='<div class="cgrid">';
    tops().forEach(function(d){
      var mine=rs.filter(function(r){return r.dept&&inTree(r.dept,d.id)});if(!mine.length)return;
      h+='<div class="ccard"><h3>'+esc(d.name)+'</h3>';var lastDept=null;
      mine.sort(function(a,b){return a.ext-b.ext}).forEach(function(r){
        if(r.dept!==lastDept&&r.dept!==d.id){h+='<h4>'+esc(dById(r.dept).name)+'</h4>';lastDept=r.dept}
        h+='<div><span><button class="who" data-ed="'+r.id+'">'+esc(r.name)+' ✎</button>'+(r.title?'<small>'+esc(r.title)+'</small>':'')+'</span><span class="x">'+nd(r.ext)+'</span></div>'});
      h+='</div>'});
    var tp=rs.filter(function(r){return !r.dept});
    if(tp.length){h+='<div class="ccard"><h3>置頂</h3>';tp.forEach(function(r){h+='<div><span><button class="who" data-ed="'+r.id+'">'+esc(r.name)+' ✎</button></span><span class="x">'+nd(r.ext)+'</span></div>'});h+='</div>'}
    h+='</div>';
  }
  $('sres').innerHTML=h;
  Array.prototype.forEach.call(document.querySelectorAll('[data-ed]'),function(b){b.onclick=function(){go('edit',{edit:+b.getAttribute('data-ed')})}});
}
function bindSearch(){
  $('q').oninput=function(){sQ=this.value;drawSearch()};
  Array.prototype.forEach.call(document.querySelectorAll('[data-m]'),function(b){b.onclick=function(){sMode=b.getAttribute('data-m');render()}});
  drawSearch();
}

/* ================= 頁面：異動收件匣 ================= */
function vInbox(){
  var pend=INBOX.filter(function(x){return x.kind==='pend'&&!x.done}),auto=INBOX.filter(function(x){return x.kind==='auto'});
  var h='<section class="wrap"><div><h1>異動收件匣</h1><div class="sub">每天早上系統比對 Domino 名冊。能判斷的已自動處理；判斷不了的在這裡等你確認。</div></div>';
  h+='<div class="box panel"><h2>待你確認 <span class="muted">'+pend.length+' 筆</span></h2>';
  if(!pend.length)h+='<div class="ok">目前沒有需要確認的異動。</div>';
  pend.forEach(function(x){h+='<div class="note"><div style="flex:1 1 360px"><span class="tag '+x.tag+'">'+x.label+'</span><b>'+esc(x.who)+'</b><div class="det">'+esc(x.det)+'</div></div><div style="display:flex;gap:8px"><button class="btn s" data-act="'+x.id+'" style="border-color:#0F6B5C;color:#0A4A40;font-weight:700">'+x.btn+'</button><button class="btn s" data-skip="'+x.id+'">略過</button></div></div>'});
  h+='</div><div class="box panel"><h2>已自動處理 <span class="muted">今天 08:00 比對</span></h2>';
  auto.forEach(function(x){h+='<div class="note"><div style="flex:1 1 360px"><span class="tag '+x.tag+'">'+x.label+'</span><b>'+esc(x.who)+'</b><div class="det">'+esc(x.det)+'</div></div><div>'+(x.done?'<span class="badge g">已還原</span>':'<button class="btn s" data-undo="'+x.id+'">還原</button>')+'</div></div>'});
  h+='<div class="muted">另有 2 位新進的 Email 為 f＋數字，已自動設為「不列入分機表」，不通知。每天一封彙整信會寄給廠務（範例信件內容與這兩段相同）。</div></div>';
  if(inboxDone.length){h+='<div class="box panel"><h2>已處理</h2>'+inboxDone.map(function(x){return '<div class="muted">'+esc(x)+'</div>'}).join('')+'</div>'}
  h+='<div class="box panel"><h2>保護機制</h2><div class="muted" style="font-size:14px;line-height:1.7">單次比對離職超過 5 人或 3%，該次全部改為待確認（防止 Domino 回傳不完整名單）。自動處理的每一筆都記在「異動紀錄」，可一鍵還原。</div></div></section>';
  return h;
}
function bindInbox(){
  Array.prototype.forEach.call(document.querySelectorAll('[data-undo]'),function(b){b.onclick=function(){
    var x=INBOX.filter(function(i){return i.id===b.getAttribute('data-undo')})[0],r=rById(x.rid);
    if(x.id==='a1'){r.active=false}else if(x.id==='a2'){r.active=true}else if(x.id==='a3'){r.dept='q1';r.ext=311}
    x.done=true;touch('廠務（範例）','還原自動處理：'+x.label+' '+x.who);toast('已還原：'+x.who);render()}});
  Array.prototype.forEach.call(document.querySelectorAll('[data-skip]'),function(b){b.onclick=function(){
    var x=INBOX.filter(function(i){return i.id===b.getAttribute('data-skip')})[0];x.done=true;inboxDone.push('略過：'+x.label+' '+x.who);touch('廠務（範例）','略過異動：'+x.label+' '+x.who);render()}});
  Array.prototype.forEach.call(document.querySelectorAll('[data-act]'),function(b){b.onclick=function(){
    var x=INBOX.filter(function(i){return i.id===b.getAttribute('data-act')})[0];
    if(x.act==='newMgr')return go('edit',{draft:{t:'P',name:'周大成（範例）',dept:'hz',title:'副理',personal:true,inbox:'p1'}});
    if(x.act==='newMgr2')return go('edit',{edit:x.rid,patch:{title:'課長',personal:true,ext:''},inbox:'p4'});
    if(x.act==='mapDept')return go('dept',{focus:'map',name:'資訊管理課'});
    if(x.act==='newHire')return go('edit',{draft:{t:'P',name:x.person,dept:x.deptId,title:'',personal:false,ext:x.defExt||'',inbox:x.id}});
    if(x.act==='renameBatch')return go('dept',{rename:'q1',to:'品質一課'});
    if(x.act==='confirmOut'){var lr=rById(x.rid);lr.active=false;x.done=true;inboxDone.push('已確認停用：'+x.who+'，個人分機 815 回到環資管理處的空號（貼牆版該列名稱變空白、號碼仍印出）');touch('廠務（範例）','確認離職停用：'+x.who+'，815 回到空號');render()}
  }});
}

/* ================= 頁面：人員與單位 ================= */
var eQ='',eDept='',eType='',eOff=false,eShow=50,eId=null,eDraft=null,eIbx=null,ePatch=null;
var ROSTER=[{n:'周大成（範例）',dep:'合四課',email:'e9001@ecic.com.tw'},{n:'王小明（範例）',dep:'品一課',email:'e9002@ecic.com.tw'},{n:'林小美（範例）',dep:'總務課',email:'e9003@ecic.com.tw'}];
function vEdit(){
  return '<section class="wrap"><div style="display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;justify-content:space-between"><div><h1>人員與單位</h1><div class="sub">人員與單位在同一頁維護，用類型篩選。你的權限：一廠廠務。</div></div><button class="btn" id="e-new">＋ 新增</button></div>'+
  '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center"><input class="in" style="flex:1 1 260px;max-width:380px" type="search" id="e-q" value="'+esc(eQ)+'" placeholder="搜尋姓名、部門、分機、Email" aria-label="搜尋"><select class="in" style="width:auto;min-width:170px" id="e-dept" aria-label="依部門篩選"><option value="">全部部門</option>'+deptOpts(eDept)+'</select>'+
  '<div class="chips" id="e-type"></div><label class="ck"><input type="checkbox" id="e-off"'+(eOff?' checked':'')+'>含已停用</label><span class="muted" id="e-count"></span></div>'+
  '<div class="cols"><div class="box scroll" style="flex:999 1 560px;min-width:0"><div style="min-width:700px" id="e-list"></div></div><div class="box panel" style="flex:1 1 360px;min-width:0" id="e-form"></div></div></section>';
}
function drawEList(){
  var all=recs.filter(function(r){return (eOff||r.active)}),k=eQ.trim().toLowerCase();
  var rs=all.filter(function(r){
    if(eType&&r.t!==eType)return false;if(eDept&&!(r.dept&&inTree(r.dept,eDept)))return false;
    return !k||[r.name,r.pn,r.title,String(r.ext),path(r.dept),r.email].some(function(s){return String(s).toLowerCase().indexOf(k)>-1})});
  rs.sort(function(a,b){return a.ext-b.ext||a.sort-b.sort});
  var h='<div class="row head" style="grid-template-columns:1.4fr 1.4fr 0.8fr 90px 1.2fr"><div>名稱</div><div>部門</div><div>職稱</div><div>分機</div><div>狀態</div></div>';
  rs.slice(0,eShow).forEach(function(r){
    var fl=[];if(!r.active)fl.push('<span class="badge r">停用</span>');if(!r.inDir)fl.push('<span class="badge g">不列入</span>');if(r.hide)fl.push('<span class="badge g">不列</span>');
    h+='<div class="row'+(eId===r.id?' sel':'')+(r.active?'':' off')+'" style="grid-template-columns:1.4fr 1.4fr 0.8fr 90px 1.2fr"><div><button class="who" data-pick="'+r.id+'">'+esc(r.name)+'</button> '+(r.t==='U'?'<span class="badge u">單位</span>':'')+'</div><div>'+esc(short(r.dept))+'</div><div>'+esc(r.title)+'</div><div class="ext">'+r.ext+' <span class="muted">'+(r.t==='P'?(r.personal?'個人':'公用'):'')+'</span></div><div>'+fl.join(' ')+'</div></div>'});
  if(rs.length>eShow)h+='<div class="row"><button class="btn s" id="e-more">顯示更多（還有 '+(rs.length-eShow)+' 筆）</button></div>';
  $('e-list').innerHTML=h;$('e-count').textContent=rs.length+' / '+all.length+' 筆';
  Array.prototype.forEach.call(document.querySelectorAll('[data-pick]'),function(b){b.onclick=function(){eId=+b.getAttribute('data-pick');eDraft=null;eIbx=null;ePatch=null;drawEList();drawForm()}});
  if($('e-more'))$('e-more').onclick=function(){eShow+=50;drawEList()};
  var t='';[['','全部'],['P','人員'],['U','單位']].forEach(function(x){t+='<button class="chip'+(eType===x[0]?' on':'')+'" data-ty="'+x[0]+'">'+x[1]+'</button>'});$('e-type').innerHTML=t;
  Array.prototype.forEach.call($('e-type').children,function(b){b.onclick=function(){eType=b.getAttribute('data-ty');drawEList()}});
}
function drawForm(){
  var r=eId?rById(eId):null,d=eDraft;
  var v=r?{t:r.t,name:r.name,pn:r.pn,dept:r.dept,title:r.title,ext:r.ext,personal:r.personal,inDir:r.inDir,hide:r.hide,note:r.note,active:r.active,email:r.email}:
    {t:(d&&d.t)||'P',name:(d&&d.name)||'',pn:'',dept:(d&&d.dept)||'',title:(d&&d.title)||'',ext:(d&&d.ext)||'',personal:d?!!d.personal:false,inDir:true,hide:false,note:'',active:true,email:''};
  if(r&&ePatch&&ePatch.id===r.id){Object.keys(ePatch).forEach(function(k){if(k!=='id')v[k]=ePatch[k]})}
  var f=$('e-form');
  f.innerHTML='<h2>'+(r?'編輯：'+esc(r.name):'新增')+'</h2>'+
  '<div class="chips"><button class="chip'+(v.t==='P'?' on':'')+'" id="t-p">人員</button><button class="chip'+(v.t==='U'?' on':'')+'" id="t-u">單位</button></div>'+
  '<div class="fld"><label for="f-name">'+(v.t==='P'?'姓名（從 Domino 名冊選）':'單位名稱')+'</label><input class="in" id="f-name" autocomplete="off" value="'+esc(v.name)+'"><div class="sug" id="f-sug"></div>'+(v.t==='P'&&v.email?'<div class="muted">已對應 Domino：'+esc(v.email)+'（範例信箱）</div>':'')+'</div>'+
  (v.t==='U'?'<div class="fld"><label for="f-pn">列印名稱（貼牆表上印的字）</label><input class="in" id="f-pn" value="'+esc(v.pn)+'"></div>':'')+
  '<div class="fld"><label for="f-dept">部門（不選＝置頂區塊）</label><select class="in" id="f-dept">'+deptOpts(v.dept,true)+'</select></div>'+
  '<div style="display:flex;gap:10px"><div class="fld" style="flex:1"><label for="f-title">職稱</label><input class="in" id="f-title" value="'+esc(v.title)+'"'+(v.t==='U'?' disabled':'')+'></div><div class="fld" style="flex:1"><label for="f-ext">分機</label><input class="in" id="f-ext" inputmode="numeric" value="'+esc(v.ext)+'"></div></div>'+
  '<div id="f-hint"></div>'+
  (v.t==='P'?'<label class="ck"><input type="checkbox" id="f-per"'+(v.personal?' checked':'')+'>有個人分機（沒勾＝使用部門公用分機，貼牆表不印這個人）</label>':'')+
  '<label class="ck"><input type="checkbox" id="f-dir"'+(v.inDir?' checked':'')+'>列入分機表</label>'+
  '<label class="ck"><input type="checkbox" id="f-hide"'+(v.hide?' checked':'')+'>貼牆表不列（EIP 仍會匯出）</label>'+
  '<div class="fld"><label for="f-note">備註</label><input class="in" id="f-note" value="'+esc(v.note)+'"></div>'+
  '<div style="display:flex;gap:10px"><button class="btn" style="flex:1" id="f-save">儲存</button>'+(r?'<button class="btn s'+(r.active?' d':'')+'" id="f-off">'+(r.active?'停用':'重新啟用')+'</button>':'')+'</div>'+
  '<div class="muted">儲存後，下次匯出的 EIP 與貼牆表會包含這筆變更。同一個分機可以有多人使用，不會被擋下。</div>';
  var typ=v.t,ibx=eIbx;
  $('t-p').onclick=function(){eDraftType('P')};$('t-u').onclick=function(){eDraftType('U')};
  function eDraftType(t){var cur=readForm(typ);cur.t=t;cur.inbox=ibx;eId=r?eId:null;eDraft=cur;if(r&&r.t!==t)return;drawForm()}
  function readForm(t){return {t:t,name:$('f-name').value,pn:$('f-pn')?$('f-pn').value:'',dept:$('f-dept').value||null,title:$('f-title').value,ext:$('f-ext').value,personal:$('f-per')?$('f-per').checked:false,inDir:$('f-dir').checked,hide:$('f-hide').checked,note:$('f-note').value}}
  function hint(){
    var dp=$('f-dept').value,e=+$('f-ext').value,tt=$('f-title').value,per=$('f-per')?$('f-per').checked:false,h='';
    var dd=dp?dById(dp):null;
    if(typ==='P'&&isMgr(tt)&&!per)h+='<div class="warn">職稱為「'+esc(tt)+'」（課長以上），應該有個人分機。</div>';
    if(dd&&e&&!inRange(e,dd.range))h+='<div class="warn">分機 '+e+' 不在「'+esc(dd.name)+'」的號段（'+dd.range+'）。只是提醒，仍可儲存。</div>';
    if(typ==='P'&&per&&dd){var em=exts.filter(function(x){return x.dept===dp&&users(x.ext).length===0}).map(function(x){return x.ext});if(em.length)h+='<div class="ok">「'+esc(dd.name)+'」的空號：'+em.join('、')+'（點一下帶入）</div>'}
    if(typ==='P'&&per&&dd&&dd.range){var rg=dd.range.split('-'),fr=[];for(var q=+rg[0];q<=+rg[1]&&fr.length<5;q++)if(!extOf(q))fr.push(q);if(fr.length)h+='<div class="ok">號段內還沒用過的號碼：'+fr.join('、')+'（點一下帶入）</div>'}
    if(typ==='P'&&!per&&dd&&dd.def&&!$('f-ext').value)h+='<div class="ok">使用部門預設分機 '+dd.def+'（點一下帶入）</div>';
    $('f-hint').innerHTML=h;
    Array.prototype.forEach.call($('f-hint').querySelectorAll('.ok'),function(o){o.style.cursor='pointer';o.onclick=function(){var m=(o.textContent.match(/\d{3}/)||[])[0];if(m){$('f-ext').value=m;hint()}}});
  }
  ['f-dept','f-ext','f-title'].forEach(function(i){$(i).oninput=hint;$(i).onchange=hint});if($('f-per'))$('f-per').onchange=hint;hint();
  $('f-name').oninput=function(){
    if(typ!=='P'){$('f-sug').innerHTML='';return}
    var q=this.value.trim(),m=q?ROSTER.concat(recs.filter(function(x){return x.t==='P'&&x.active}).slice(0,60).map(function(x){return {n:x.name,dep:short(x.dept),email:x.email}})).filter(function(x){return x.n.indexOf(q)>-1}).slice(0,5):[];
    $('f-sug').style.display=m.length?'flex':'none';
    $('f-sug').innerHTML=m.map(function(x,i){return '<button data-s="'+i+'">'+esc(x.n)+'　<span class="muted">'+esc(x.dep)+'　'+esc(x.email)+'</span></button>'}).join('');
    Array.prototype.forEach.call($('f-sug').children,function(b){b.onclick=function(){var x=m[+b.getAttribute('data-s')];$('f-name').value=x.n;$('f-sug').innerHTML='';$('f-sug').style.display='none'}});
  };
  $('f-sug').style.display='none';
  $('f-save').onclick=function(){
    var x=readForm(typ);if(!x.name.trim()||!+x.ext){toast('請填名稱與分機');return}
    x.ext=+x.ext;
    if(r){r.name=x.name;r.pn=x.pn;r.dept=x.dept;r.title=x.title;r.ext=x.ext;r.personal=x.personal;r.inDir=x.inDir;r.hide=x.hide;r.note=x.note;
      if(r.t==='P'&&r.personal&&isMgr(r.title)&&r.dept)r.sort=topSort(r.dept);
      if(!extOf(x.ext))exts.push({ext:x.ext,dept:x.dept,grade:'',note:''});
      touch('廠務（範例）','修改 '+(r.t==='U'?'單位':'人員')+'：'+r.name+(r.title?'（'+r.title+'）':'')+'，分機 '+r.ext);
      if(ibx)closeInbox(ibx,(r.personal?'個人分機 ':'分機 ')+r.ext)}
    else{var n={id:++nid,t:typ,name:x.name,pn:x.pn,dept:x.dept,title:x.title,ext:x.ext,personal:typ==='P'?x.personal:false,inDir:x.inDir,hide:x.hide,active:true,sort:3000+nid,note:x.note,email:typ==='P'?'e'+(1000+nid)+'@ecic.com.tw':''};recs.push(n);
      if(!extOf(x.ext))exts.push({ext:x.ext,dept:x.dept,grade:'',note:''});eId=n.id;touch('廠務（範例）','新增 '+(typ==='U'?'單位':'人員')+'：'+n.name+'，分機 '+n.ext);
      if(n.t==='P'&&n.personal&&isMgr(n.title)&&n.dept)n.sort=topSort(n.dept);
      if(ibx)closeInbox(ibx,(n.personal?'個人分機 ':'分機 ')+n.ext)}
    eDraft=null;eIbx=null;ePatch=null;toast('已儲存（範例）');drawEList();drawForm();renderNav();
  };
  if(r&&$('f-off'))$('f-off').onclick=function(){r.active=!r.active;touch('廠務（範例）',(r.active?'重新啟用：':'停用：')+r.name);drawEList();drawForm()};
}
function bindEdit(){
  $('e-q').oninput=function(){eQ=this.value;eShow=50;drawEList()};
  $('e-dept').onchange=function(){eDept=this.value;eShow=50;drawEList()};
  $('e-off').onchange=function(){eOff=this.checked;drawEList()};
  $('e-new').onclick=function(){eId=null;eDraft=null;eIbx=null;ePatch=null;drawEList();drawForm();$('f-name').focus()};
  if(goArg&&goArg.edit){eId=goArg.edit;eDraft=null;eQ='';eDept='';eType='';eIbx=goArg.inbox||null;ePatch=goArg.patch?Object.assign({id:goArg.edit},goArg.patch):null}
  else if(goArg&&goArg.draft){eId=null;eDraft=goArg.draft;eIbx=goArg.draft.inbox||null;ePatch=null}
  goArg=null;
  $('e-q').value=eQ;$('e-dept').value=eDept;drawEList();drawForm();
}

/* ================= 頁面：部門表 ================= */
var dMove=null,dFocus=null;
function headCount(id){return recs.filter(function(r){return r.active&&r.dept===id}).length}
function treeCount(id){return recs.filter(function(r){return r.active&&r.dept&&inTree(r.dept,id)}).length}
function vDept(){
  var h='<section class="wrap"><div><h1>部門表（一廠）</h1><div class="sub">決定分機表上怎麼分區、怎麼排序。這是分機表的顯示分組，不是人事的正式組織架構。依貼牆表展開。</div></div><div class="ok hide" id="d-from" style="line-height:1.7"></div><div class="box panel hide" id="d-move" style="border-color:var(--acc)"></div>'+
  '<div class="cols"><div class="box scroll" style="flex:999 1 620px;min-width:0"><div style="min-width:680px" id="d-list"></div></div>'+
  '<div class="box panel" style="flex:1 1 300px;min-width:0"><h2>新增部門</h2><div class="fld"><label for="d-par">上層部門</label><select class="in" id="d-par">'+deptOpts('',true)+'</select></div><div class="fld"><label for="d-name">部門名稱</label><input class="in" id="d-name" placeholder="例如：製五組"></div><button class="btn" id="d-add">新增</button><div class="muted">新增在同層最後面，再用 ↑ ↓ 調整。改名只要改一次，底下人員自動跟著變。底下還有人員或單位時不能停用，只停用、不刪除。</div></div></div>'+
  '<div class="box panel" id="d-map"></div></section>';
  return h;
}
var MAPD=[{n:'資訊管理課',c:1}],MAPD_DONE=[];
function hdrForced(d){return kids(d.id).length>0||recs.some(function(r){return r.active&&r.t==='P'&&r.personal&&r.dept===d.id})}
function hdrBox(d){var f=hdrForced(d);return '<label class="ck" style="font-size:12px;color:var(--mut);margin-top:3px"><input type="checkbox" data-hd="'+d.id+'"'+((d.hdr!==false||f)?' checked':'')+(f?' disabled title="底下有子部門或有個人分機的人員，一定要印標題列"':'')+'>印標題列</label>'}
function drawDept(){
  var h='<div class="row head" style="grid-template-columns:1.5fr 90px 110px 80px 250px"><div>部門</div><div>預設分機</div><div>號段</div><div>人員／單位</div><div>操作</div></div>';
  flat().forEach(function(x,i){var d=x.d,sibs=(d.parent?kids(d.parent):tops()),ix=sibs.indexOf(d);
    var ue=recs.filter(function(r){return r.active&&r.t==='U'&&r.dept===d.id}).map(function(r){return r.ext});
    var sel='<select class="in" style="height:34px;padding:0 6px" data-def="'+d.id+'"><option value="">未設定</option>'+ue.map(function(e){return '<option'+(d.def===e?' selected':'')+'>'+e+'</option>'}).join('')+(d.def&&ue.indexOf(d.def)<0?'<option selected>'+d.def+'</option>':'')+'</select>';
    h+='<div class="row" style="grid-template-columns:1.5fr 90px 110px 80px 250px"><div style="padding-left:'+(x.lv*22)+'px">'+(x.lv?'└ ':'')+esc(d.name)+hdrBox(d)+'</div><div>'+sel+'</div><div><input class="in" style="height:34px" data-rg="'+d.id+'" value="'+esc(d.range||'')+'" placeholder="210-219"></div><div class="muted">'+headCount(d.id)+' ／ '+treeCount(d.id)+'</div><div style="display:flex;flex-wrap:wrap;gap:6px"><button class="btn s" data-up="'+d.id+'"'+(ix===0?' disabled':'')+' aria-label="上移">↑</button><button class="btn s" data-dn="'+d.id+'"'+(ix===sibs.length-1?' disabled':'')+' aria-label="下移">↓</button><button class="btn s" data-rn="'+d.id+'">改名</button><button class="btn s" data-mv="'+d.id+'">移動</button><button class="btn s d" data-off="'+d.id+'">停用</button></div></div>'});
  $('d-list').innerHTML=h;
  var m='<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 16px;align-items:baseline"><h2>Domino 部門名稱對照</h2><div class="muted">Domino 只有部門名稱、沒有階層。名稱相同自動對應；對不上的由廠務指定，對應一次後記住。</div></div>';
  MAPD.forEach(function(x){m+='<div class="note"><div><span class="tag mv">未對應</span><b>'+esc(x.n)+'</b>　<span class="muted">'+x.c+' 人</span></div><div style="display:flex;gap:8px;align-items:center"><select class="in" style="width:auto;max-width:260px" data-mp="'+esc(x.n)+'"><option value="">＋ 新增為部門（放在最上層）</option>'+flat().map(function(f){return '<option value="'+f.d.id+'">指定到：'+'　'.repeat(f.lv)+esc(f.d.name)+'</option>'}).join('')+'</select><button class="btn s" data-mpa="'+esc(x.n)+'">確定</button></div></div>'});
  MAPD_DONE.forEach(function(x){m+='<div class="muted">已對應：Domino「'+esc(x.n)+'」→ '+esc(path(x.to))+'</div>'});
  if(!MAPD.length&&!MAPD_DONE.length)m+='<div class="ok">全部對得上。</div>';
  $('d-map').innerHTML=m;
  var q=function(s,f){Array.prototype.forEach.call(document.querySelectorAll(s),f)};
  q('[data-hd]',function(c){c.onchange=function(){var d=dById(c.getAttribute('data-hd'));d.hdr=c.checked;touch('廠務（範例）','設定「'+d.name+'」貼牆版'+(c.checked?'印':'不印')+'標題列');toast(c.checked?'貼牆版會印這個部門的標題列':'貼牆版不印標題列，只印底下的單位列（範例）')}});
  q('[data-up]',function(b){b.onclick=function(){swap(b.getAttribute('data-up'),-1)}});
  q('[data-dn]',function(b){b.onclick=function(){swap(b.getAttribute('data-dn'),1)}});
  q('[data-rn]',function(b){b.onclick=function(){var d=dById(b.getAttribute('data-rn')),n=prompt('「'+d.name+'」改名為：',d.name);if(n&&n!==d.name)renameDept(d.id,n)}});
  q('[data-off]',function(b){b.onclick=function(){var d=dById(b.getAttribute('data-off'));if(treeCount(d.id)||recs.some(function(r){return r.active&&r.dept===d.id})||kids(d.id).length){toast('底下還有人員、單位或子部門，不能停用');return}d.active=false;touch('廠務（範例）','停用部門：'+d.name);drawDept()}});
  q('[data-mv]',function(b){b.onclick=function(){openMove(b.getAttribute('data-mv'))}});
  q('[data-def]',function(s){s.onchange=function(){var d=dById(s.getAttribute('data-def'));d.def=s.value?+s.value:null;touch('廠務（範例）','設定「'+d.name+'」預設分機：'+(d.def||'未設定'));toast('已設定（範例）')}});
  q('[data-rg]',function(s){s.onchange=function(){var d=dById(s.getAttribute('data-rg'));d.range=s.value;touch('廠務（範例）','設定「'+d.name+'」號段：'+s.value)}});
  q('[data-mpa]',function(b){b.onclick=function(){
    var n=b.getAttribute('data-mpa'),sel=document.querySelector('[data-mp="'+n+'"]'),dd;
    if(sel.value){dd=dById(sel.value)}
    else{dd={id:'n'+(++nid),name:n,parent:null,fill:null,col:0,def:null,range:'',sort:2000+nid,active:true,hdr:true};depts.push(dd);touch('廠務（範例）','新增部門：'+n)}
    mapDomino(n,dd,!sel.value);drawDept();renderNav()}});
}
function mapDomino(n,dd,isNew){
  if(!MAPD.some(function(x){return x.n===n}))return false;
  MAPD=MAPD.filter(function(x){return x.n!==n});MAPD_DONE.push({n:n,to:dd.id});
  touch('廠務（範例）','Domino 部門「'+n+'」對應到 '+path(dd.id));
  var p2=INBOX.filter(function(i){return i.id==='p2'&&!i.done})[0];
  if(p2){closeInbox('p2',(isNew?'新增為部門「':'對應到「')+path(dd.id)+'」');
    INBOX.push({id:'p6',kind:'pend',tag:'new',label:'新進・補分機',who:'吳小芬（範例）',person:'吳小芬（範例）',deptId:dd.id,defExt:dd.def||'',
      det:'Domino 部門「'+n+'」已對應到「'+path(dd.id)+'」。'+(dd.def?'這個部門的預設分機是 '+dd.def+'，':'這個部門還沒有設定預設分機，')+'請補上分機後加入「人員與單位」。',btn:'新增人員與分機',act:'newHire'});
    toast('部門已對應，異動收件匣多了一筆「新進・補分機」，請到收件匣處理');renderNav()}
  return true;
}
function swap(id,dir){var d=dById(id),sibs=d.parent?kids(d.parent):tops(),i=sibs.indexOf(d),o=sibs[i+dir];if(!o)return;var t=d.sort;d.sort=o.sort;o.sort=t;touch('廠務（範例）','調整順序：'+d.name+(dir<0?' 上移':' 下移'));drawDept()}
function renameDept(id,n){var d=dById(id),old=d.name;
  if(depts.some(function(x){return x.active&&x.parent===d.parent&&x.name===n&&x.id!==id})){toast('同層已有同名部門');return}
  d.name=n;mapDomino(n,d,false);touch('廠務（範例）','部門改名：「'+old+'」→「'+n+'」（底下 '+treeCount(id)+' 人自動跟著變）');toast('已改名，底下人員自動跟著變');drawDept()}
function openMove(id){
  var d=dById(id),box=$('d-move');box.classList.remove('hide');
  var h='<h2>移動「'+esc(d.name)+'」</h2><div class="muted">連同底下 '+(depts.filter(function(x){return x.active&&x.id!==id&&inTree(x.id,id)}).length)+' 個子部門與 '+treeCount(id)+' 位人員／單位一起搬。</div><div class="fld"><label for="mv-to">搬到哪個上層（或最上層）</label><select class="in" id="mv-to"><option value="">（最上層）</option>';
  flat().forEach(function(x){if(inTree(x.d.id,id))return;h+='<option value="'+x.d.id+'">'+'　'.repeat(x.lv)+esc(x.d.name)+'</option>'});
  h+='</select></div><div id="mv-w"></div><div style="display:flex;gap:10px"><button class="btn" id="mv-ok">搬過去</button><button class="btn o" id="mv-no">取消</button></div>';
  box.innerHTML=h;
  $('mv-no').onclick=function(){box.classList.add('hide')};
  $('mv-ok').onclick=function(){var to=$('mv-to').value||null;
    if(depts.some(function(x){return x.active&&x.parent===to&&x.name===d.name&&x.id!==id})){$('mv-w').innerHTML='<div class="warn">目的地已有同名部門，不能搬。</div>';return}
    d.parent=to;d.sort=1000+nid++;if(to===null){d.col=0}touch('廠務（範例）','移動部門：「'+d.name+'」→ '+(to?path(to):'最上層'));box.classList.add('hide');drawDept();toast('已移動，分機表與貼牆表自動換位置')};
  box.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function bindDept(){
  $('d-add').onclick=function(){var n=$('d-name').value.trim(),p=$('d-par').value||null;if(!n)return;
    if(depts.some(function(x){return x.active&&x.parent===p&&x.name===n})){toast('同層已有同名部門');return}
    depts.push({id:'n'+(++nid),name:n,parent:p,fill:null,col:0,def:null,range:'',sort:2000+nid,active:true,hdr:true});touch('廠務（範例）','新增部門：'+n+(p?'（上層：'+dById(p).name+'）':''));mapDomino(n,depts[depts.length-1],true);$('d-name').value='';drawDept()};
  drawDept();
  if(goArg&&goArg.rename){var id=goArg.rename,to=goArg.to;goArg=null;var d=dById(id);if(confirm('把 9 人整批套用，並將部門「'+d.name+'」改名為「'+to+'」？（範例）')){renameDept(id,to);INBOX.forEach(function(i){if(i.id==='p5'){i.done=true;inboxDone.push('已整批套用：「品一課」改名為「'+to+'」，9 人自動跟著變')}});renderNav()}}
  else if(goArg&&goArg.focus==='map'){var nm=goArg.name||'';goArg=null;
    if(nm){$('d-name').value=nm;var fb=$('d-from');fb.classList.remove('hide');
      fb.innerHTML='<b>來自異動收件匣：</b>新進的部門「'+esc(nm)+'」在部門表裡沒有對應。兩種做法擇一：<br>① 在下方「Domino 部門名稱對照」，指定到既有部門，或選「＋ 新增為部門」按「確定」。<br>② 在右邊「新增部門」按「新增」。名稱已幫你填好「'+esc(nm)+'」，同名會自動對應。'}
    $('d-map').scrollIntoView({behavior:'smooth'})}
}

/* ================= 頁面：分機號碼表 ================= */
var xQ='',xF='';
function vExt(){
  return '<section class="wrap"><div style="display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;justify-content:space-between"><div><h1>分機號碼表</h1><div class="sub">每一支分機的所屬部門、等級與狀態。這張表本身不印，但「空號」會印在貼牆表上（名稱留空，只有分機與等級）。狀態由系統計算：有人員或單位使用是「使用中」，沒有就是「空號」。</div></div></div>'+
  '<div class="box panel" style="gap:8px"><div class="muted" style="font-size:14px;line-height:1.7"><b>等級 A／B</b> 表示這支分機能否撥打外線，記在分機號碼上，改一次所有使用者跟著變。系統只記錄與列印，實際撥號權限仍由交換機設定。<br><b>號段</b>是約定俗成：百位數對應最上層部門、十位數對應課。號碼放到別的部門號段時只提醒，不擋。</div></div>'+
  '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center"><input class="in" style="flex:1 1 240px;max-width:340px" type="search" id="x-q" value="'+esc(xQ)+'" placeholder="搜尋分機、部門、使用者" aria-label="搜尋"><div class="chips" id="x-f"></div><span class="muted" id="x-n"></span></div>'+
  '<div class="cols"><div class="box scroll" style="flex:999 1 640px;min-width:0"><div style="min-width:720px" id="x-list"></div></div>'+
  '<div class="box panel" style="flex:1 1 280px"><h2>新增分機號碼</h2><div class="fld"><label for="x-new">分機號碼</label><input class="in" id="x-new" inputmode="numeric"></div><div class="fld"><label for="x-nd">所屬部門</label><select class="in" id="x-nd">'+deptOpts('',true)+'</select></div><div class="fld"><label for="x-ng">等級</label><select class="in" id="x-ng"><option value="">未填</option><option>A</option><option>B</option></select></div><button class="btn" id="x-add">新增</button><div class="muted">所屬部門會依號段自動建議。新進人員要個人分機時，系統列出該部門的空號供挑選。</div></div></div></section>';
}
function suggestDept(e){var m=null;depts.forEach(function(d){if(d.active&&d.range&&inRange(e,d.range)){if(!m||(d.parent&&!m.parent))m=d}});return m}
function drawExt(){
  var rows=exts.map(function(x){var u=users(x.ext);return {x:x,u:u,st:u.length?'使用中':'空號'}}),k=xQ.trim().toLowerCase();
  var all=rows.length;
  rows=rows.filter(function(r){if(xF&&r.st!==xF)return false;return !k||String(r.x.ext).indexOf(k)>-1||path(r.x.dept).toLowerCase().indexOf(k)>-1||r.u.some(function(z){return z.name.toLowerCase().indexOf(k)>-1})});
  var h='<div class="row head" style="grid-template-columns:70px 70px 1.4fr 80px 1.6fr 1fr"><div>分機</div><div>等級</div><div>所屬部門</div><div>狀態</div><div>使用者</div><div>備註</div></div>';
  rows.forEach(function(r){var x=r.x,out=x.dept&&!inRange(x.ext,dById(x.dept).range);var nm=r.u.map(function(z){return z.name}),us=nm.length>3?nm.slice(0,3).join('、')+' 等 '+nm.length+' 筆':nm.join('、');
    h+='<div class="row" style="grid-template-columns:70px 70px 1.4fr 80px 1.6fr 1fr"><div class="ext">'+x.ext+'</div><div><select class="in" style="height:34px;padding:0 6px" data-gr="'+x.ext+'"><option value="">—</option><option'+(x.grade==='A'?' selected':'')+'>A</option><option'+(x.grade==='B'?' selected':'')+'>B</option></select></div><div><select class="in" style="height:34px;padding:0 6px" data-xd="'+x.ext+'">'+deptOpts(x.dept,true)+'</select>'+(out?'<div class="muted" style="color:#7A4B00">不在號段 '+esc(dById(x.dept).range)+'</div>':'')+'</div><div><span class="badge'+(r.st==='空號'?' u':'')+'">'+r.st+'</span></div><div class="muted" style="font-size:13px">'+esc(us)+'</div><div><input class="in" style="height:34px" data-xn="'+x.ext+'" value="'+esc(x.note)+'"></div></div>'});
  $('x-list').innerHTML=h;$('x-n').textContent=rows.length+' / '+all+' 支';
  var c='';[['','全部'],['使用中','使用中'],['空號','空號']].forEach(function(f){c+='<button class="chip'+(xF===f[0]?' on':'')+'" data-xf="'+f[0]+'">'+f[1]+'</button>'});$('x-f').innerHTML=c;
  var q=function(s,f){Array.prototype.forEach.call(document.querySelectorAll(s),f)};
  q('[data-xf]',function(b){b.onclick=function(){xF=b.getAttribute('data-xf');drawExt()}});
  q('[data-gr]',function(s){s.onchange=function(){var x=extOf(+s.getAttribute('data-gr'));x.grade=s.value;touch('廠務（範例）','分機 '+x.ext+' 等級改為 '+(s.value||'未填')+'（'+users(x.ext).length+' 個使用者跟著變）');toast('已改，使用這支分機的人一起變（範例）')}});
  q('[data-xd]',function(s){s.onchange=function(){var x=extOf(+s.getAttribute('data-xd'));x.dept=s.value||null;touch('廠務（範例）','分機 '+x.ext+' 所屬部門改為 '+path(x.dept));drawExt()}});
  q('[data-xn]',function(s){s.onchange=function(){var x=extOf(+s.getAttribute('data-xn'));x.note=s.value;touch('廠務（範例）','分機 '+x.ext+' 備註：'+s.value)}});
}
function bindExt(){
  $('x-q').oninput=function(){xQ=this.value;drawExt()};
  $('x-new').oninput=function(){var e=+this.value,d=suggestDept(e);if(d)$('x-nd').value=d.id};
  $('x-add').onclick=function(){var e=+$('x-new').value;if(!e)return;if(extOf(e)){toast('這支分機已經在表裡');return}
    var dd=$('x-nd').value||null;exts.push({ext:e,dept:dd,grade:$('x-ng').value,note:'空號'});exts.sort(function(a,b){return a.ext-b.ext});touch('廠務（範例）','新增分機號碼 '+e+'（'+path(dd)+'）');$('x-new').value='';drawExt()};
  drawExt();
}

/* ================= 頁面：列印版面 ================= */
var layTab=1,ori2='l';
function vLayout(){
  return '<section class="wrap"><div><h1>列印版面</h1><div class="sub">以最上層部門為一塊，整塊放在同一欄、不拆開。決定每塊放第幾欄與順序，再看預覽與列印前檢查。</div></div>'+
  '<div style="display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center"><div class="chips" role="tablist"><button class="chip'+(layTab===1?' on':'')+'" data-lt="1">列印版 1：貼牆版</button><button class="chip'+(layTab===2?' on':'')+'" data-lt="2">列印版 2：新風格</button></div>'+
  (layTab===2?'<div class="chips" role="group" aria-label="紙張方向"><button class="chip'+(ori2==='l'?' on':'')+'" data-o="l">橫式（4 欄）</button><button class="chip'+(ori2==='p'?' on':'')+'" data-o="p">直式（3 欄）</button></div>':'')+'</div>'+
  '<div class="cols"><div style="flex:1 1 380px;min-width:0;display:flex;flex-direction:column;gap:16px"><div class="box panel" id="l-blocks"></div><div class="box panel" id="l-checks"></div></div>'+
  '<div style="flex:999 1 640px;min-width:0"><div class="sheetbar" style="margin-bottom:10px"><div class="muted">'+(layTab===1?'A4 直式、縮放 80%、一頁印完。':'A4 '+(ori2==='l'?'橫式':'直式')+'，列高與字級自動調整到一頁放得下。')+'實際輸出為 Excel；這裡是版面預覽（白色範圍就是一頁）。</div><div style="display:flex;gap:8px"><button class="btn s" onclick="window.print()">列印／存成 PDF</button></div></div><div class="sheetscroll" id="l-sheet"></div></div></div></section>';
}
function drawLayout(){if(layTab===2)drawLayout2();else drawLayout1()}
function drawLayout1(){
  var L=layout(),h='<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px"><h2>各欄內容</h2><button class="btn s" id="l-bal">自動平衡欄高</button></div>';
  for(var c=1;c<=3;c++){var n=L.counts[c-1];h+='<div><div style="display:flex;justify-content:space-between;font-weight:700;margin:6px 0"><span>第 '+c+' 欄</span><span class="muted" style="color:'+(n>52?'#B3261E':'var(--mut)')+'">'+n+' 列'+(n>52?'（過長）':'')+'</span></div>';
    var bl=L.blocks.filter(function(b){return b.col===c-1});
    if(c===1&&L.cols[0].length&&L.cols[0][0].dept===null)h+='<div class="note" style="padding:6px 12px"><span>（置頂：緊急專線、總機、廠長、副廠長）</span><span class="muted">'+L.cols[0][0].rows.length+' 列</span></div>';
    bl.forEach(function(b,i){h+='<div class="note" style="padding:6px 12px;margin-top:4px"><span>'+esc(b.d.name)+' <span class="muted">'+b.rows.length+' 列</span></span><span style="display:flex;gap:4px;align-items:center"><button class="btn s" data-bu="'+b.d.id+'"'+(i===0?' disabled':'')+' aria-label="上移">↑</button><button class="btn s" data-bd="'+b.d.id+'"'+(i===bl.length-1?' disabled':'')+' aria-label="下移">↓</button><select class="in" style="height:34px;width:78px;padding:0 6px" data-bc="'+b.d.id+'" aria-label="換欄"><option value="1"'+(c===1?' selected':'')+'>第1欄</option><option value="2"'+(c===2?' selected':'')+'>第2欄</option><option value="3"'+(c===3?' selected':'')+'>第3欄</option></select></span></div>'});
    h+='</div>'}
  $('l-blocks').innerHTML=h;
  var ck=checks(),k='<h2>列印前檢查 <span class="muted">'+(ck.length?ck.length+' 項提醒':'')+'</span></h2>';
  if(!ck.length)k+='<div class="ok">沒有警告。</div>';ck.forEach(function(x){k+='<div class="warn">'+esc(x.t)+'</div>'});
  k+='<div class="muted">警告只提醒、不擋匯出。</div>';$('l-checks').innerHTML=k;
  $('l-sheet').innerHTML=sheet1();fit();
  var q=function(s,f){Array.prototype.forEach.call(document.querySelectorAll(s),f)};
  q('[data-bc]',function(s){s.onchange=function(){var d=dById(s.getAttribute('data-bc'));d.col=+s.value;var mx=0;tops().forEach(function(t){if(t.col===d.col&&t!==d)mx=Math.max(mx,t.ord||0)});d.ord=mx+1;touch('廠務（範例）','貼牆版：「'+d.name+'」移到第 '+d.col+' 欄');drawLayout()}});
  q('[data-bu]',function(b){b.onclick=function(){mv(b.getAttribute('data-bu'),-1)}});q('[data-bd]',function(b){b.onclick=function(){mv(b.getAttribute('data-bd'),1)}});
  $('l-bal').onclick=function(){var bs=layout().blocks.slice().sort(function(a,b){return (a.d.col-b.d.col)||(a.d.ord-b.d.ord)}),len=[0,0,0],top=layout().cols[0].filter(function(x){return x.dept===null}).reduce(function(s,x){return s+x.rows.length},0);len[0]=top;
    bs.forEach(function(b){var m=len.indexOf(Math.min.apply(null,len));b.d.col=m+1;b.d.ord=len[m]+1;len[m]+=b.rows.length});
    var o={};bs.forEach(function(b){o[b.d.col]=(o[b.d.col]||0)+1;b.d.ord=o[b.d.col]});touch('廠務（範例）','貼牆版：自動平衡欄高');drawLayout();toast('已依序填入最短的欄')};
}
function mv(id,dir){var d=dById(id),sib=tops().filter(function(t){return t.col===d.col}).sort(function(a,b){return a.ord-b.ord}),i=sib.indexOf(d),o=sib[i+dir];if(!o)return;var t=d.ord;d.ord=o.ord;o.ord=t;touch('廠務（範例）','貼牆版：調整「'+d.name+'」順序');drawLayout()}
function fit(){Array.prototype.forEach.call(document.querySelectorAll('.sheetscroll'),function(w){var s=w.firstElementChild;if(!s)return;var a=w.clientWidth,need=s.classList.contains('landscape')?1123:794;s.style.zoom=a&&a<need?a/need:1})}
window.addEventListener('resize',fit);
/* ----- 列印版 2：分欄 ----- */
var P2={l:null,p:null};
function p2Blocks(){
  var out=[],tp=recs.filter(function(r){return printable(r)&&!r.dept}).sort(function(a,b){return a.sort-b.sort});
  if(tp.length)out.push({id:'_top',name:'置頂',rows:tp.map(rowOfRec),lines:tp.length+1});
  tops().forEach(function(d){var rows=blockRows(d,0).filter(function(r){return r.k!=='e'});out.push({id:d.id,name:d.name,rows:rows,lines:rows.length})});
  return out;
}
function p2N(o){return o==='l'?4:3}
function autoBal2(o){
  var N=p2N(o),bs=p2Blocks(),tot=bs.reduce(function(s,b){return s+b.lines+1},0),tg=tot/N,cur=0,c=0,cfg={},cnt=[0,0,0,0];
  bs.forEach(function(b){if(cur>0&&c<N-1&&cur+(b.lines+1)/2>tg){c++;cur=0}cfg[b.id]={c:c+1,o:++cnt[c]};cur+=b.lines+1});
  P2[o]=cfg;
}
function p2Cols(o){
  if(!P2[o])autoBal2(o);
  var N=p2N(o),cfg=P2[o],cols=[];for(var i=0;i<N;i++)cols.push([]);
  p2Blocks().forEach(function(b){var k=cfg[b.id]||(cfg[b.id]={c:1,o:99});b.k=k;cols[Math.min(N,k.c)-1].push(b)});
  cols.forEach(function(c){c.sort(function(a,b){return a.k.o-b.k.o})});
  var avail=o==='l'?690:1010,w=cols.map(function(c){return c.reduce(function(s,b){return s+b.lines+0.7},0)}),mx=Math.max.apply(null,w);
  var raw=Math.floor(avail/mx),rh=Math.max(13,Math.min(24,raw));
  return {N:N,cols:cols,w:w,rh:rh,over:raw<13,mx:mx,avail:avail};
}
function sheet2(o){
  var P=p2Cols(o),h='<div class="sheet '+(o==='p'?'portrait':'landscape')+' p2" style="--rh:'+P.rh+'px;--f:'+(P.rh*0.62).toFixed(1)+'px"><div class="tt"><b>'+esc(PLANT.name)+'分機表</b><span class="muted">'+fmtDate()+'</span></div><div class="g">';
  P.cols.forEach(function(c){h+='<div class="pc">';c.forEach(function(b){
    h+='<div class="c"><h3>'+esc(b.name)+'</h3>';
    b.rows.forEach(function(r,i){if(r.k==='h1')return;if(r.k==='h2')h+='<h5>'+esc(r.text)+'</h5>';else h+='<div class="i'+(r.k==='u'?' u':'')+'"><span>'+esc(r.text)+'</span><span class="x">'+nd(r.ext)+'</span></div>'});
    h+='</div>'});h+='</div>'});
  h+='</div><div class="foot">'+PLANT.foot.slice(0,3).map(esc).join('　｜　')+'</div></div>';
  return h;
}
function drawLayout2(){
  var P=p2Cols(ori2),h='<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px"><h2>各欄內容（'+(ori2==='l'?'橫式':'直式')+'）</h2><button class="btn s" id="l-bal">自動平衡欄高</button></div>';
  P.cols.forEach(function(c,i){h+='<div><div style="display:flex;justify-content:space-between;font-weight:700;margin:6px 0"><span>第 '+(i+1)+' 欄</span><span class="muted">'+c.reduce(function(s,b){return s+b.lines},0)+' 列</span></div>';
    c.forEach(function(b,j){h+='<div class="note" style="padding:6px 12px;margin-top:4px"><span>'+esc(b.name)+' <span class="muted">'+b.lines+' 列</span></span><span style="display:flex;gap:4px;align-items:center"><button class="btn s" data-bu="'+b.id+'"'+(j===0?' disabled':'')+' aria-label="上移">↑</button><button class="btn s" data-bd="'+b.id+'"'+(j===c.length-1?' disabled':'')+' aria-label="下移">↓</button><select class="in" style="height:34px;width:78px;padding:0 6px" data-bc="'+b.id+'" aria-label="換欄">'+P.cols.map(function(_,k){return '<option value="'+(k+1)+'"'+(k===i?' selected':'')+'>第'+(k+1)+'欄</option>'}).join('')+'</select></span></div>'});
    h+='</div>'});
  $('l-blocks').innerHTML=h;
  var ck=checks().filter(function(x){return x.t.indexOf('欄')<0});
  if(P.over)ck.push({t:'內容太多，一頁放不下（列高已縮到最小 13px）。正式版會自動接到第二頁；可以改用另一個方向，或把欄調平均。'});
  var k='<h2>列印前檢查 <span class="muted">'+(ck.length?ck.length+' 項提醒':'')+'</span></h2><div class="'+(P.over?'warn':'ok')+'">目前列高 '+P.rh+'px（約 '+(P.rh*0.62*0.75).toFixed(1)+' pt 字），'+(P.over?'超過一頁':'一頁放得下')+'。</div>';
  ck.forEach(function(x){k+='<div class="warn">'+esc(x.t)+'</div>'});k+='<div class="muted">警告只提醒、不擋匯出。</div>';$('l-checks').innerHTML=k;
  $('l-sheet').innerHTML=sheet2(ori2);fit();
  var q=function(s,f){Array.prototype.forEach.call(document.querySelectorAll(s),f)};
  var nm=function(id){return id==='_top'?'置頂':dById(id).name};
  q('[data-bc]',function(s){s.onchange=function(){var id=s.getAttribute('data-bc'),cfg=P2[ori2],mx=0;Object.keys(cfg).forEach(function(x){if(cfg[x].c===+s.value&&x!==id)mx=Math.max(mx,cfg[x].o)});cfg[id]={c:+s.value,o:mx+1};touch('廠務（範例）','新風格版：「'+nm(id)+'」移到第 '+s.value+' 欄');drawLayout2()}});
  var mv2=function(id,dir){var cfg=P2[ori2],c=cfg[id].c,sib=Object.keys(cfg).filter(function(x){return cfg[x].c===c}).sort(function(a,b){return cfg[a].o-cfg[b].o}),i=sib.indexOf(id),o=sib[i+dir];if(!o)return;var t=cfg[id].o;cfg[id].o=cfg[o].o;cfg[o].o=t;touch('廠務（範例）','新風格版：調整「'+nm(id)+'」順序');drawLayout2()};
  q('[data-bu]',function(b){b.onclick=function(){mv2(b.getAttribute('data-bu'),-1)}});q('[data-bd]',function(b){b.onclick=function(){mv2(b.getAttribute('data-bd'),1)}});
  $('l-bal').onclick=function(){autoBal2(ori2);touch('廠務（範例）','新風格版：自動平衡欄高');drawLayout2();toast('已依序平均分到各欄')};
}
function bindLayout(){
  if(goArg&&goArg.tab){layTab=goArg.tab;goArg=null;render();return}
  Array.prototype.forEach.call(document.querySelectorAll('[data-lt]'),function(b){b.onclick=function(){layTab=+b.getAttribute('data-lt');render()}});
  Array.prototype.forEach.call(document.querySelectorAll('[data-o]'),function(b){b.onclick=function(){ori2=b.getAttribute('data-o');render()}});
  drawLayout();
}

/* ================= 頁面：匯出 / 版 2 ================= */
var lastExport='2026-11-07 17:30',ori2='l';
function vExport(){
  var n=recs.filter(function(r){return r.active&&r.inDir}).length,pr=layout().counts.reduce(function(a,b){return a+b},0);
  return '<section class="wrap"><div><h1>匯出</h1><div class="sub">檔案由系統即時從資料庫整理，下載到的一定是目前網站上的最新資料。</div></div>'+
  '<div class="box panel" style="flex-direction:row;flex-wrap:wrap;gap:8px 28px;align-items:center"><div><b>一廠</b>　目前 '+n+' 筆列入分機表</div><div class="muted">上次匯出：'+lastExport+'</div><div class="'+(changed?'warn':'ok')+'" style="padding:6px 12px">上次匯出後又改了 '+changed+' 筆</div></div>'+
  '<div class="cards">'+
  '<div class="box card"><div class="k">給入口網站</div><div class="t">EIP 上傳檔</div><p>欄位：廠區／分公司、部門、姓名、職稱、市話、分機、簡碼、備註。部門以「\\」分層。列出所有「列入分機表」的人員與單位，「貼牆表不列」不影響這份。</p><div class="warn">上傳到入口網站會<strong>覆蓋整個廠區</strong>。請確認網站上的資料是最新的再匯出。</div><div style="flex:1"></div><button class="btn" data-dl="EIP 上傳檔">下載 .xlsx</button></div>'+
  '<div class="box card"><div class="k">列印</div><div class="t">列印版 1：貼牆版</div><p>對齊現有貼牆表：A4 直式、三組（單位名稱／分機號碼／等級）、黃底部門列、檔尾撥號規則。預覽約 '+pr+' 列，欄位與分欄在「列印版面」調整。</p><div style="flex:1"></div><button class="btn s" style="width:fit-content" data-go="layout">到列印版面看預覽</button><button class="btn o" data-dl="貼牆版">下載 .xlsx</button></div>'+
  '<div class="box card"><div class="k">列印</div><div class="t">列印版 2：新風格</div><p>依部門分區塊卡片，分機放大，單位與人員用顏色區分，遠處也看得清楚。橫式四欄、直式三欄，資料多時自動換頁。</p><div style="flex:1"></div><button class="btn s" style="width:fit-content" data-go="p2">看預覽</button><button class="btn o" data-dl="新風格版">下載 .xlsx</button></div></div></section>';
}
function bindExport(){
  Array.prototype.forEach.call(document.querySelectorAll('[data-go]'),function(b){b.onclick=function(){go(b.getAttribute('data-go'))}});
  Array.prototype.forEach.call(document.querySelectorAll('[data-dl]'),function(b){b.onclick=function(){lastExport=TODAY+' '+('0'+(new Date().getHours())).slice(-2)+':'+('0'+(new Date().getMinutes())).slice(-2);changed=0;touch('廠務（範例）','匯出：'+b.getAttribute('data-dl'));changed=0;toast('範例畫面：正式版會下載 Excel。已記錄匯出時間。');render()}});
}
/* ================= 頁面：異動紀錄 ================= */
function vLog(){
  var h='<section class="wrap"><div><h1>異動紀錄</h1><div class="sub">誰（含系統自動處理）在何時改了什麼。這個畫面上的操作也會即時出現在這裡。</div></div><div class="box scroll"><div style="min-width:620px"><div class="row head" style="grid-template-columns:150px 130px 1fr"><div>時間</div><div>誰</div><div>內容</div></div>';
  LOG.forEach(function(x){h+='<div class="row" style="grid-template-columns:150px 130px 1fr"><div class="muted">'+esc(x.t)+'</div><div>'+(x.who==='系統'?'<span class="badge b">系統</span>':esc(x.who))+'</div><div>'+esc(x.what)+'</div></div>'});
  return h+'</div></div></section>';
}

/* ================= 主流程 ================= */
function render(){
  renderNav();var m=$('main');
  var map={search:[vSearch,bindSearch],inbox:[vInbox,bindInbox],edit:[vEdit,bindEdit],dept:[vDept,bindDept],ext:[vExt,bindExt],layout:[vLayout,bindLayout],export:[vExport,bindExport],log:[vLog,function(){}]};
  var v=map[view];m.innerHTML=v[0]();v[1]();window.scrollTo(0,0);
  try{history.replaceState(null,'','#'+view)}catch(e){}
}
var h0=(location.hash||'').slice(1);if(h0&&['search','inbox','edit','dept','ext','layout','export','log'].indexOf(h0)>-1)view=h0;
window.__demo={recs:recs,depts:depts,exts:exts,layout:layout,checks:checks,go:go};
render();
})();
