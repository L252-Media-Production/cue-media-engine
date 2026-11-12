
async function j(u,o){return (await fetch(u,o)).json()}
/* Page lock: while a modal dialog (or the tour) dims the page, the page behind it does not scroll (wheel, touch, keys, rubber-banding) and its exact
   scroll position comes back on close. ONE helper with a counter, so two overlays open together do not unlock early. The document is fixed in place at
   its scroll position (body{position:fixed;top:-y}, the only method iOS respects); html keeps a (idle) scrollbar track so nothing shifts sideways. Every
   <dialog> opened with showModal() is covered by the wrapper below; the tour calls pageLock / pageUnlock itself. */
const PGLOCK={n:0,y:0};
function pageLock(){if(PGLOCK.n++)return;const b=document.body;PGLOCK.y=window.scrollY;b.style.top=-PGLOCK.y+'px';document.documentElement.classList.add('plock');b.classList.add('plock')}
function pageUnlock(){if(PGLOCK.n===0||--PGLOCK.n)return;const b=document.body;document.documentElement.classList.remove('plock');b.classList.remove('plock');b.style.top='';window.scrollTo(0,PGLOCK.y)}
/* ---- 2.7.5 rc1: Live output / Preview buttons, Preview meters while previewing, Preview Mute, the pinned Live panel and its one-line strip */
function outOpen(sel,btn){cbOpenSel(sel,btn)}
/* The infinity sign of the dB scale comes from whatever font has it, so its glyph sits higher or lower than the digits: move it by the difference of the real ink centres (canvas metrics), so it is centred on its dB level like the numbers. */
function fitInf(){try{const inf=document.querySelector('#lvl .dbs .inf');if(!inf)return;const b=inf.parentNode,cs=getComputedStyle(b),ci=getComputedStyle(inf),c=document.createElement('canvas').getContext('2d');
 const m=(ch,s)=>{c.font=s.fontWeight+' '+s.fontSize+' '+s.fontFamily;const r=c.measureText(ch);return (r.actualBoundingBoxAscent-r.actualBoundingBoxDescent)/2};
 inf.style.top=(m('\u221e',ci)-m('0',cs)).toFixed(2)+'px'}catch(e){}}
function pvmSync(){      // the Preview pair (bars, label, Mute and output button, one-line chip) shows only while previewing, or while Solo live uses the preview output
 const on=['playing','paused','loading'].includes(PVCUR.state)||pv.classList.contains('solo');
 lvl.classList.toggle('pvon',on);pvlvl.hidden=!on;pcap.hidden=!on;pvbtns.hidden=!on;ms_pv.hidden=!on}
var pvMuted=false;
function pvMuteUi(){pvmute.classList.toggle('muted',pvMuted);pvmute.setAttribute('aria-pressed',pvMuted);try{AU.muted=pvMuted;for(const a of MONA.values())a.muted=pvMuted}catch(e){}}
async function pvMute(){pvMuted=!pvMuted;pvMuteUi();if(PVDEV){try{await fetch('/api/preview/ctl',{method:'POST',body:JSON.stringify({cmd:'mute',on:pvMuted})})}catch(e){}}}
var PINKEEP=(()=>{try{return localStorage.getItem('cp_pinkeep')!=='0'}catch(e){return true}})();
var PIN=(()=>{try{return PINKEEP?localStorage.getItem('cp_pin')!=='0':true}catch(e){return true}})();
var PINMINI=(()=>{try{return localStorage.getItem('cp_pinmini')!=='0'}catch(e){return true}})();
var PASSED=false;
function lsSet(k,v){try{if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){}}
function pinSet(on){PIN=!!on;if(PINKEEP)lsSet('cp_pin',PIN?'1':'0');pinUi()}
function pinToggle(){pinSet(!PIN)}
function pinOpt(k,v){if(k==='mini'){PINMINI=!!v;lsSet('cp_pinmini',PINMINI?'1':'0')}else if(k==='keep'){PINKEEP=!!v;lsSet('cp_pin',PINKEEP?(PIN?'1':'0'):null);lsSet('cp_pinkeep',PINKEEP?'1':'0')}pinUi()}
function pinUi(){
 for(const b of [pinbtn,ms_pin]){b.classList.toggle('on',PIN);b.classList.toggle('off',!PIN);b.setAttribute('aria-pressed',PIN);
  b.setAttribute('aria-label',PIN?'Unpin the Live panel':'Pin the Live panel');b.title=PIN?'Pinned: the Live panel stays in view while you scroll. Click to unpin.':'Not pinned. Click to keep the Live panel in view while you scroll.'}
 document.body.classList.toggle('pinfull',PIN&&!PINMINI);   // pinned but not shrinking: the whole panel stays at the top
 if(window.set_pin){set_pin.checked=PIN;set_pinmini.checked=PINMINI;set_pinkeep.checked=PINKEEP;setSums()}
 mstripShow()}
function mstripShow(){ms.hidden=!(PIN&&PINMINI&&PASSED)}
function mstripSync(s){
 if(!window.ms)return;
 ms_name.textContent=livenm.textContent;asLink(ms_name,livenm.classList.contains('lk'),livenm.title);if(ms_name.classList.contains('lk'))ms_name.setAttribute('aria-label','Show '+(livenm.textContent||'the playing track')+' in its playlist');else ms_name.removeAttribute('aria-label');ms_pp.innerHTML=s.state==='paused'?LI.play:LI.pause;ms_pp.title=s.state==='paused'?'Resume':'Pause';
 ms_rem.textContent=remv.textContent;const tl=(s.live_out||0)-(s.live_in||0),tot=s.live_dur?(tl>0.5&&tl<s.live_dur-0.5?tl:s.live_dur):0;ms_tot.textContent=tot?' / '+mmss(tot):'';
 ms.classList.toggle('idle',s.state==='stopped');ms_pill.textContent=s.state==='paused'?'PAUSED':'LIVE'}
/* the one-line bar shows when MORE THAN HALF of the full panel has scrolled out of the top of the view and goes when less than half is out. The observer is told at 48 % and 52 % visible (a few percent of hysteresis, so nothing flickers at 50 %); it does not depend on scroll events and the bar is fixed, so no layout moves. */
try{new IntersectionObserver(es=>{const e=es[es.length-1];PASSED=e.boundingClientRect.top<0&&e.intersectionRatio<0.5;mstripShow()},{threshold:[0,0.48,0.52,1]}).observe(document.getElementById('cl'))}catch(e){}
(()=>{const o=HTMLDialogElement.prototype.showModal;HTMLDialogElement.prototype.showModal=function(){const was=this.open;o.call(this);if(!was&&this.open){pageLock();this.addEventListener('close',pageUnlock,{once:true})}}})();
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const escAttr=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function bytes(n){const u=['B','KB','MB','GB','TB'];let i=0;n=+n;while(n>=1024&&i<4){n/=1024;i++}return (i<2?Math.round(n):n.toFixed(1))+' '+u[i]}
const SV=(d,x='')=>`<svg width=18 height=18 viewBox="0 0 24 24" fill=currentColor stroke=currentColor stroke-width=2 stroke-linejoin=round stroke-linecap=round>${d}</svg>`;
const LI={pause:SV('<rect x=6 y=5 width=4 height=14 rx=1 stroke=none /><rect x=14 y=5 width=4 height=14 rx=1 stroke=none />'),
 play:SV('<path d="M7 4.5v15l12-7.5z"/>'),
 fade:SV('<path d="M5 4v16h15z"/>'),
 stop:SV('<rect x=5 y=5 width=14 height=14 rx=2 stroke=none />'),
 take:SV('<path d="M4 5l11 7-11 7z" stroke=none /><path d="M19 5v14" fill=none stroke-width=3 />'),
 xf:'<svg width=20 height=16 viewBox="0 0 24 18" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round><path d="M2 3h5c6 0 8 12 15 12"/><path d="M2 15h5c6 0 8-12 15-12"/></svg>',
 vol:SV('<path d="M4 9v6h4l5 4V5L8 9z" stroke=none /><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11" fill=none />'),
 mute:SV('<path d="M4 9v6h4l5 4V5L8 9z" stroke=none /><path d="M16 9l5 6M21 9l-5 6" fill=none />')};
{const b=document.querySelectorAll('.tbar button.ic');[LI.pause,LI.fade,LI.stop].forEach((h,i)=>b[i].innerHTML=h);document.querySelector('#ms .msstop').innerHTML=LI.stop;ms_pp.innerHTML=LI.pause}
let GO='cut';
function goSync(g){g=g==='crossfade'?'crossfade':'cut';GO=g;gocol.classList.toggle('cut',g==='cut');go_tg.classList.toggle('xf',g==='crossfade');
 const h=(g==='cut'?LI.take:LI.xf)+'<span>'+(g==='cut'?'Cut':'Fade')+'</span>';if(go_tg._h!==h){go_tg._h=h;go_tg.innerHTML=h}
 go_tg.title=g==='cut'?'Go cuts to the cued track. Click to make Go crossfade instead.':'Go crossfades to the cued track. Click to make Go cut instead.'}
function goSet(g){goSync(g);fetch('/api/go_transition/'+g)}
function goNow(){const x=cuePT();if(x&&!x.t.missing&&x.t.ram&&x.t.ram!=='in'){GOLOAD={t:Date.now(),id:LASTS&&LASTS.focus_id};goBusy()}cmd(GO==='crossfade'?'xfade':'take')}
// RAM indicator (2.7.3): display only. A cue that is not in RAM waits for its decode exactly as before; the Go button just says so.
let GOLOAD=null,lastRamRev=-1;
const GOHINT='Cued track is not in RAM yet. It starts as soon as it is decoded.';
function goBusy(){
 const b=document.querySelector('.cuego');if(!b)return;
 if(GOLOAD){const s=LASTS||{},el=Date.now()-GOLOAD.t;if(s.loading==='-'&&(s.live_id===GOLOAD.id||el>1200)||el>120000)GOLOAD=null}
 const on=!!GOLOAD,h=on?`<i class=gsp aria-hidden=true></i><span>Loading… ${Math.floor((Date.now()-GOLOAD.t)/1000)} s</span>`:'Go';
 if(b._h!==h){b._h=h;b.innerHTML=h}
 b.classList.toggle('wait',on);b.setAttribute('aria-busy',on);
 b.title=on?GOHINT:'Go: play the cue track now, cutting or crossfading as chosen beside it';
 if(on)prepmsg.textContent=GOHINT}
setInterval(()=>{if(GOLOAD)goBusy()},250);
const RAMTIP={in:'In RAM, starts instantly',loading:'Loading',out:'Not loaded, starts after a short wait'};
function ramDot(t){return t.missing||!t.ram||t.ram==='in'?'':`<span class="rd ${t.ram}" role=img title="${RAMTIP[t.ram]}" aria-label="${RAMTIP[t.ram]}"></span>`}
let PGD={},lastLiveId='';

// ---- Playlist progress (2.7.3): all sums are done here from /api/playlists (dur_eff = the A-to-B window) and the live position; nothing runs in the engine.
const PGMODE={stop:'Stop at end',loop_playlist:'Loop',shuffle:'Shuffle',next_playlist:'Next playlist'};
const pgT=x=>{x=Math.max(0,Math.round(x));const h=Math.floor(x/3600),m=Math.floor(x%3600/60),sec=x%60;return h?h+':'+String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0'):m+':'+String(sec).padStart(2,'0')};
const pgLen=t=>(t.dur_eff||0)*(t.end==='once'?2:1);          // "once" plays the track twice
function plLive(i){const m=/^(\d+)\/(\d+)$/.exec((LASTS&&LASTS.live_id)||'');return m&&+m[1]===i&&PL[i]&&PL[i].tracks[+m[2]]?+m[2]:-1}
function plDone(i,s){   // indices of tracks of playlist i that are already played in this run
 if(PGD[i])return PGD[i];const p=PL[i],cur=(()=>{const m=/^(\d+)\/(\d+)$/.exec((s&&s.live_id)||'');return m&&+m[1]===i?+m[2]:-1})(),d=new Set();
 if(p&&cur>=0){if(p.mode==='shuffle'&&p.shuffle_left){const left=new Set(p.shuffle_left);p.tracks.forEach((t,k)=>{if(k!==cur&&!left.has(t.id))d.add(k)})}
  else if(p.mode!=='shuffle')for(let k=0;k<cur;k++)d.add(k)}
 return PGD[i]=d}
function plProgHtml(p,i){
 const n=p.tracks.length,one=n>40,w=t=>Math.max(0.5,t.dur_eff||1);
 const segs=n?(one?'<i class=seg style="flex:1"><b></b></i>':p.tracks.map(t=>`<i class=seg style="flex:${w(t)}"><b></b></i>`).join('')):'';
 return `<div class=plprog data-i=${i}><div class=ppl><span class=ppt></span><span class=ppm title="What happens when a track in this playlist ends">${PGMODE[p.mode]||p.mode}</span></div><div class="pbar${one?' one':''}" aria-hidden=true>${segs}</div>${plRam(p)}</div>`}
function plProg(i){   // numbers for playlist i from the live state
 const p=PL[i];if(!p)return null;const n=p.tracks.length,L=p.tracks.map(pgLen),total=L.reduce((a,b)=>a+b,0),cur=plLive(i);
 const r={n,total,cur,mode:p.mode,L};
 if(cur<0)return r;
 const t=p.tracks[cur],win=t.dur_eff||0,passes=Math.max(1,LASTS.live_passes||1),pass=Math.max(1,LASTS.live_pass||1);
 const pos=LIVE.pos+(LIVE.playing?(performance.now()-LIVE.t0)/1000:0);
 r.el=Math.min(win*passes,Math.max(0,pos-(LIVE.lo||0))+(pass-1)*win);r.win=win*passes;r.loopTrack=t.end==='loop';r.curLeft=Math.max(0,r.win-r.el);
 r.done=plDone(i,LASTS);let before=0,after=0;
 if(p.mode==='shuffle'){const left=new Set(p.shuffle_left||[]);p.tracks.forEach((x,k)=>{if(k===cur)return;if(r.done.has(k))before+=L[k];else if(left.has(x.id))after+=L[k]})}
 else{for(let k=0;k<cur;k++)before+=L[k];let stop=false;for(let k=cur+1;k<n&&!stop;k++){after+=L[k];if(p.tracks[k].end==='stop')stop=true}
  if(p.tracks[cur].end==='stop')after=0}
 r.before=before;r.after=after;r.played=before+r.el;r.left=r.loopTrack?null:r.curLeft+after;
 r.pos=r.played/Math.max(1,before+r.win+after);
 r.num=p.mode==='shuffle'?r.done.size+1:cur+1;
 return r}
function plProgTick(all){
 if(!PL.length||!document.getElementById('lists'))return;
 setTimeout(fitSub,0);
 const live=LASTS?plLive0():-1;
 document.querySelectorAll('#lists .plprog').forEach(el=>{
  const i=+el.dataset.i;if(!all&&i!==live)return;
  const g=plProg(i);if(!g)return;const p=PL[i],segs=el.querySelectorAll('.seg'),ppt=el.querySelector('.ppt');
  let txt;
  if(g.cur<0){txt=g.n?`${g.n} track${g.n===1?'':'s'} · ${pgT(g.total)} total`:'empty';
   segs.forEach(sg=>{sg.classList.remove('cur','done');sg.firstChild.style.width='0'})}
  else{
   const end=g.left==null?'':new Date(Date.now()+g.left*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
   const next=p.mode==='next_playlist'&&PL[i+1]?` → ${PL[i+1].name}`:'';
   txt=`Track ${g.num} of ${g.n} · ${pgT(g.played)} played · `+(g.left==null?'looping this track':`${pgT(g.left)} left${p.mode==='loop_playlist'?' this lap':p.mode==='shuffle'?' this round':''} · ends ${end}${next}`);
   if(segs.length===1){segs[0].firstChild.style.width=(g.pos*100).toFixed(2)+'%';segs[0].classList.add('cur')}
   else segs.forEach((sg,k)=>{const d=g.done.has(k),c=k===g.cur;sg.classList.toggle('done',d);sg.classList.toggle('cur',c);sg.firstChild.style.width=d?'100%':c?(g.win?g.el/g.win*100:0).toFixed(2)+'%':'0'})}
  if(ppt.textContent!==txt)ppt.textContent=txt;
  if(all||i===live){const li=document.querySelector(`#lists li.t.live[data-i="${i}"]`);if(li&&g.cur>=0){const pe=li.querySelector('.rpe'),pl=li.querySelector('.rpl b');
   if(pe){const t=`▶ ${pgT(g.el)} / ${pgT(g.win)}`;if(pe.textContent!==t)pe.textContent=t}if(pl)pl.style.width=(g.win?g.el/g.win*100:0).toFixed(2)+'%'}}})}
function plLive0(){const m=/^(\d+)\//.exec((LASTS&&LASTS.live_id)||'');return m?+m[1]:-1}
setInterval(()=>plProgTick(false),250);
function plRam(p){return p.ram_total?`<span class=plram title="Tracks of this playlist decoded in RAM start instantly; the others wait for a short decode">${p.ram_in} of ${p.ram_total} in RAM</span>`:''}
let RAMV={st:null,rdy:0,tm:0};      // what the pill shows; rdy = when the ready state began (loading -> ready waits 2 s, the other way is at once)
function ramShow(r){
 if(!r)return;
 let st=r.full?'full':(r.loading&&r.tracks_in_ram<r.tracks_total)?'loading':r.tracks_in_ram>=r.tracks_total?'ready':'part';
 const now=Date.now();clearTimeout(RAMV.tm);
 if(st==='ready'||st==='part'){
  if(RAMV.st==='loading'){if(!RAMV.rdy)RAMV.rdy=now;
   if(now-RAMV.rdy<2000){st='loading';RAMV.tm=setTimeout(()=>ramShow(LASTRAM),RAMV.rdy+2000-now+20)}}}
 else RAMV.rdy=0;
 if(st==='ready'||st==='part')RAMV.rdy=0;
 LASTRAM=r;RAMV.st=st;
 const n=r.tracks_in_ram,m=r.tracks_total,txt=st==='full'?'Full':n+'/'+m,pct=m?Math.min(100,n/m*100):0;
 const tip=st==='full'?'Cache full. The oldest tracks are dropped to make room. Tracks not in RAM start after a short wait.':n+' of '+m+' tracks in RAM. Tracks not in RAM start after a short wait.';
 ramchip.hidden=!m;mem_cachew.classList.toggle('full',st==='full');
 const k=st+'|'+txt+'|'+Math.round(pct);if(ramchip._k===k)return;ramchip._k=k;
 ramchip.dataset.st=st;ramchip.querySelector('.rct').textContent=txt;ramchip.querySelector('.rcb b').style.width=pct+'%';
 ramchip.title=tip;ramchip.setAttribute('aria-label',tip)}
let LASTRAM=null;
goSync('cut');
const PVI={pause:'<svg width=16 height=16 viewBox="0 0 24 24" fill=currentColor><rect x=5 y=4 width=5 height=16 rx=1.2 /><rect x=14 y=4 width=5 height=16 rx=1.2 /></svg>',play:'<svg width=16 height=16 viewBox="0 0 24 24" fill=currentColor><path d="M7 4.5v15l12-7.5z"/></svg>',solo:'<svg width=18 height=18 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M11 5L6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 010 7"/><path d="M19 5a10 10 0 010 14"/></svg>'};
const setPP=paused=>{const h=paused?PVI.play:PVI.pause;if(pvpp.innerHTML!==h)pvpp.innerHTML=h};
setPP(false);
const LUI=(d,fill)=>`<svg width=16 height=16 viewBox="0 0 24 24" fill=${fill||'none'} stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round>${d}</svg>`;
/* Library header: Collapse all is Lucide minimize-2 (arrows in), Expand all is its mirror, maximize-2 (arrows out); same 16 px, stroke 2 */
const IC={collapse:LUI('<path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="m14 10 7-7"/><path d="m3 21 7-7"/>'),expand:LUI('<path d="M15 3h6v6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/><path d="M9 21H3v-6"/>'),
 star:LUI('<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.9L12 17.8 5.8 21.1 7 14.2 2 9.3l6.9-1z"/>'),starOn:LUI('<path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.9L12 17.8 5.8 21.1 7 14.2 2 9.3l6.9-1z"/>','currentColor'),
 eye:LUI('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'),eyeOff:LUI('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><path d="m3 3 18 18"/>'),trim:'<svg width=18 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M8 4H4v16h4"/><path d="M16 4h4v16h-4"/><path d="M9 12h6"/></svg>',loop:'<svg width=18 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/></svg>',play:'PVW',
 pause:'<svg width=13 height=13 viewBox="0 0 24 24" fill=currentColor><rect x=5.5 y=4 width=4.5 height=16 rx=1.2 /><rect x=14 y=4 width=4.5 height=16 rx=1.2 /></svg>'};
foctrbtn.innerHTML=IC.trim;   // the Cue panel's Trim button uses the same icon as the playlist rows
IC.ea={default:'<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>',once:'<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/><path d="M11 10h1v4"/></svg>',loop:'<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M6 16c5 0 7-8 12-8a4 4 0 0 1 0 8c-5 0-7-8-12-8a4 4 0 1 0 0 8"/></svg>',stop:'<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><circle cx=12 cy=12 r=10 /><rect x=9 y=9 width=6 height=6 rx=1 /></svg>'};
const EA_TIP={default:'Then play the next track (follows the playlist)',once:'Loop once, then continue',loop:'Loop forever',stop:'Stop at this track'};
const EA_NEXT={default:'once',once:'loop',loop:'stop',stop:'default'};
const eaBtn=(i,k,e)=>{e=e||'default';return `<button class="ib ea ${e}" onclick="cmd('${i}/${k}/end')" title="${EA_TIP[e]}. Click for: ${EA_TIP[EA_NEXT[e]]}" aria-label="${EA_TIP[e]}">${IC.ea[e]}</button>`};
IC.cplay='<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M9 9.003a1 1 0 0 1 1.517-.859l4.997 2.997a1 1 0 0 1 0 1.718l-4.997 2.997A1 1 0 0 1 9 14.996z"/><circle cx=12 cy=12 r=10 /></svg>';
IC.shuf='<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22"/><path d="M2 6h1.972a4 4 0 0 1 3.6 2.2"/><path d="M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45"/></svg>';
IC.info='<svg width=15 height=15 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><circle cx=12 cy=12 r=10 /><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';
let TRFADE=1500,TRFADEIN=0,PVTRIM=null,TR=null,PVCUR={id:null,state:'stopped'},LIBC={},LIBI={},FLASH={path:null,id:null,until:0},WAVE=false,PVST={pos:0,dur:0,state:'stopped',t0:0},LIVE={fid:null,pos:0,dur:0,lo:0,hi:0,playing:false,t0:0},WF={},scrub=null;
try{WAVE=localStorage.getItem('cp_wave')==='1'}catch(e){}
document.body.classList.toggle('wave',WAVE);
function folderColor(id){let d=id.includes('/')?id.slice(0,id.lastIndexOf('/')):'';while(d){if(LIBC[d])return LIBC[d];d=d.includes('/')?d.slice(0,d.lastIndexOf('/')):''}return ''}
function markPv(){                    // the preview button of the track being previewed shows pause (or play when paused)
 for(const el of document.querySelectorAll('.lt,li.t')){const b=el.querySelector('.ib.pv');if(!b)continue;
  const same=(el.dataset.id||el.dataset.fid)===PVCUR.id&&PVCUR.id!=null,on=same&&(PVCUR.state==='playing'||PVCUR.state==='loading'),paused=same&&PVCUR.state==='paused';
  const want=on?'pause':'play';if(b.dataset.ic!==want){b.dataset.ic=want;b.innerHTML=IC[want]}
  b.classList.toggle('on',on||paused);b.title=on?'Pause the preview':paused?'Resume the preview':'Preview this track (PVW)'}
 pvInfoSync();pvSync();pvmSync()}
let PVROW=null,pvKey='',pvJump=false;
function pvWantKey(){if(!PVROW||!PVCUR.id||!['playing','paused','loading'].includes(PVCUR.state))return '';
 const p=PL[PVROW.p],t=p&&p.tracks[PVROW.t];return t&&t.id===PVCUR.id?PVROW.p+'/'+PVROW.t:''}
function pvHome(){const m=document.querySelector('.pvmain');if(m&&m.parentNode!==pv){pv.append(m)}pv.classList.remove('docked');pvstub.hidden=true;pvInfoRender()}
function pvDock(){const slot=lists.querySelector('.pvslot');
 if(!slot){pvHome();return}
 const m=document.querySelector('.pvmain');if(m.parentNode!==slot)slot.append(m);
 pv.classList.add('docked');pvstub.hidden=false;pvInfoRender();
 const p=PL[PVROW.p],t=p&&p.tracks[PVROW.t];
 pvstub.innerHTML='<span>🎧 <b>Preview</b> is open under <b>'+esc(t?t.name:'')+'</b> in '+esc(p?p.name:'')+'</span><button onclick="pvShow()">Show</button>';
 if(pvJump){pvJump=false;const li=slot.closest('li');if(li)li.scrollIntoView({block:'nearest',behavior:'smooth'})}}
function pvShow(){const li=lists.querySelector('.pvslot');if(li)li.closest('li').scrollIntoView({block:'center',behavior:'smooth'})}
function pvSync(){const k=pvWantKey();if(k!==pvKey){pvKey=k;if(k)pvJump=true;lastHtml='';if(typeof LASTS==='object'&&LASTS&&LASTS.live_id!==undefined)renderLists(LASTS);else pvDock()}}
const MODES=[['stop','Stop'],['loop_playlist','Loop Playlist'],['next_playlist','Next Playlist'],['shuffle','Shuffle']];
let PVDEV=null,pvState='stopped',pvSeeking=false,PL=[],LIBF=[],STORE=null,SCAN={},lastRev=-1,lastStore=0,lastHtml='',lastLib='',dragging=null,scanHidden='',curScanKey='';

const LIBNARROW=matchMedia("(max-width:34rem)");LIBNARROW.addEventListener("change",()=>{if(STORE)renderStore()});
function renderStore(){
 const s=STORE;if(!s)return;
 const cap=s.cap, pct=cap?s.used/cap*100:(s.disk_total-s.disk_free)/s.disk_total*100;
 const low=s.allowance<50*1048576,cls=(s.over||pct>=95||low)?'crit':pct>=80?'warn':'';
 libsum.innerHTML=LIBNARROW.matches?`<b>${bytes(s.used)}</b>`+(cap?` of ${bytes(cap)}`:'')+` &middot; ${s.files}`:`<b>${bytes(s.used)}</b>`+(cap?` of <b>${bytes(cap)}</b> cap (${Math.round(pct)}%)`:'')+` &middot; ${s.files} file(s)`;
 libsum.hidden=false;libcount.hidden=true;             // the count is in the summary: one count only
 const tip=`Disk ${bytes(s.disk_free)} free of ${bytes(s.disk_total)} \u00b7 room for uploads: ${bytes(s.allowance)}`+(s.limited_by==='cap'?' (library cap)':` (${bytes(s.reserve)} kept free)`);
 libhd.title=tip;
 const w=s.over?'Library is over its cap':low?`Low room for uploads: ${bytes(s.allowance)}`:'';
 libwarn.textContent=w;libwarn.hidden=!w;libwarn.title=tip;
 libhd.classList.toggle('warn',cls==='warn');libhd.classList.toggle('crit',cls==='crit');
 libbar.hidden=!(cap||cls);libbar.firstChild.style.width=Math.min(100,pct).toFixed(1)+'%'}
const few=a=>(a.length>5?a.slice(0,5).concat(['and '+(a.length-5)+' more']):a).map(esc).join(', ');
function renderScan(){
 const m=[],s=SCAN||{};
 if((s.new||[]).length)m.push(`${s.new.length} new file(s) found in the library: ${few(s.new)}`);
 if((s.gone||[]).length)m.push(`${s.gone.length} file(s) no longer in the library: ${few(s.gone)}`);
 for(const [k,v] of Object.entries(s.missing||{}))m.push(`Playlist "${esc(k)}" has track(s) whose file is missing: ${few(v)}`);
 curScanKey=m.join('|');
 scan.innerHTML=(m.length&&curScanKey!==scanHidden)?`<div class=notice>${m.join('<br>')}<button onclick="scanHidden=curScanKey;renderScan()">Dismiss</button></div>`:'';
}
let SEL=new Set(),selAnchor=null;let LIBD=[],closed=new Set();try{closed=new Set(JSON.parse(localStorage.getItem('cp_closed')||'[]'))}catch(e){}
const saveClosed=()=>{try{localStorage.setItem('cp_closed',JSON.stringify([...closed]))}catch(e){}};
const byName=(a,b)=>a.name.toLowerCase().localeCompare(b.name.toLowerCase());
function fileRow(x,depth,flat,num,dim){
 const dir=x.id.includes('/')?x.id.slice(0,x.id.lastIndexOf('/')):'';
 return `<div class="lt${dim?' hid':''}${SEL.has(x.id)?' sel':''}${FLASH.id===x.id&&Date.now()<FLASH.until?' flash':''}" draggable=true data-id="${esc(x.id)}" style="padding-left:${depth*14+4}px"><span class=grip title="Drag into a playlist, or onto a folder">⠿</span>${num?`<span class=lnum>${num}</span>`:''}
  <span class=ln title="${esc(x.id+(x.fmt&&x.fmt.tip?'  ·  '+x.fmt.tip:''))}">${esc(x.name)}${flat&&dir?` <small class=dim>${esc(dir)}</small>`:''}</span><span class="sz ldr">${LIBDUR[x.id]?dtxt(LIBDUR[x.id]):''}</span>
  ${x.fmt&&(x.fmt.lv==='warn'||x.fmt.lv==='error')?`<span class="fmtw ${x.fmt.lv}" title="${esc(x.fmt.msg+(x.fmt.tip?' ('+x.fmt.tip+')':''))}">${x.fmt.lv==='error'?'⛔':'⚠'}</span>`:(LIBDUR[x.id]===0?'<span class="fmtw error" title="This file could not be read">⛔</span>':'')}
  ${x.used&&x.used.length?`<button class="ib inpl" data-act=inpl title="In ${x.used.length} playlist(s): ${esc([...x.used].sort((a,b)=>a-b).map(n=>PL[n]?PL[n].name:n).join(', '))}. Click to find it in each playlist, one at a time.">▤<b>${x.used.length}</b></button>`:''}
  <button class="ib inf" data-info="${esc(x.id)}" title="File information" aria-label="File information">${IC.info}</button>
  <button class="ib pv" data-act=pv data-ic=play title="Preview this track (PVW)">${IC.play}</button>
  ${PL.length?`<span class=ib title="Add to a playlist">＋<select data-act=add><option value="">Add to…</option>${PL.map((p,n)=>`<option value=${n}>${esc(p.name)}</option>`).join('')}</select></span>`:''}
  <button class=ib data-act=ren title="Rename or move to another folder">✎</button>
  <button class="ib del" data-act=del title="Delete this file from the library">✕</button></div>`}
/* ---- Library folder flags (2.7.4): favorite and hidden live on the player (LIBFL, shared by every browser); collapsed state, the Hidden toggle are per device ---- */
let LIBFL={},HIDSHOW=false,SREV=false;try{HIDSHOW=localStorage.getItem('cp_lib_hidden')==='1'}catch(e){}
const flOf=p=>LIBFL[p]||{};
const upOf=p=>p.includes('/')?p.slice(0,p.lastIndexOf('/')):'';
function hidTop(p){const segs=p?p.split('/'):[];let cur='';for(const sg of segs){cur=cur?cur+'/'+sg:sg;if(flOf(cur).hidden)return cur}return ''}
const isHid=p=>!!hidTop(p);
const hiddenN=()=>Object.keys(LIBFL).filter(k=>LIBFL[k].hidden&&LIBD.includes(k)).length;
const visDir=d=>HIDSHOW||!isHid(d.path);
function folderRow(d,depth,o){
 o=o||{};const fl=flOf(d.path),hid=isHid(d.path),own=!!fl.hidden,open=!o.noTog&&!closed.has(d.path);
 const acts=own?`<button class="ib unhide" data-act=unhide title="Hidden. Click to unhide" aria-label="Hidden. Click to unhide: ${esc(d.name)}">${IC.eyeOff}</button>`
  :`<button class="ib star${fl.fav?' on':''}" data-act=fav title="${fl.fav?'Unfavorite':'Favorite'}" aria-label="${fl.fav?'Unfavorite':'Favorite'}: ${esc(d.name)}" aria-pressed="${!!fl.fav}">${fl.fav?IC.starOn:IC.star}</button><button class="ib hide" data-act=hide title="Hide" aria-label="Hide: ${esc(d.name)}">${IC.eyeOff}</button>`
  +`<button class=ib data-act=newf title="New folder in here">＋</button><button class=ib data-act=renf title="Rename or move this folder">✎</button>
   <button class="ib del" data-act=delf title="${d.n||d.dirs.size?'Delete this folder and everything in it (you will be asked to confirm)':'Delete this empty folder'}">✕</button>`;
 return `<div class="fd${hid?' hid':''}${FLASH.path===d.path&&Date.now()<FLASH.until?' flash':''}" ${o.noTog?'':'draggable=true '}data-path="${esc(d.path)}" style="padding-left:${depth*14+4}px">${o.noTog?'':`<span class=fdt data-act=tog>${open?'▾':'▸'}</span>`}
   <span class="cdot${LIBI[d.path]&&ICONS[LIBI[d.path]]?' ico':''}" data-act=color ${LIBC[d.path]?`style="--fc:${LIBC[d.path]}"`:''} title="Folder colour and icon (the colour shows as a flag on the playlist rows)">${icoSvg(LIBI[d.path],14)}</span>
   <b data-act=tog title="${esc(d.path)}">${esc(o.label||d.name)}</b>${own?'<span class=hbadge>hidden</span>':''}<small>${o.count!=null?o.count:d.n}</small>
   <span class=fda>${acts}</span></div>`}
function libRows(n,depth,out,skipFav){
 for(const d of [...n.dirs.values()].sort(byName)){
  if(!visDir(d)||(skipFav&&flOf(d.path).fav))continue;
  const open=!closed.has(d.path);
  out.push(folderRow(d,depth));
  if(open)libRows(d,depth+1,out,skipFav)}
 n.files.sort(byName).forEach((x,i)=>out.push(fileRow(x,depth,false,depth>0?i+1:0,isHid(upOf(x.id)))))}
function favDirs(root){const o=[];const walk=n=>{for(const d of n.dirs.values()){if(flOf(d.path).fav&&visDir(d))o.push(d);walk(d)}};walk(root);return o.sort(byName)}
function searchRows(f){
 const m=LIBF.filter(x=>x.id.toLowerCase().includes(f)).sort(byName),rows=[];
 const hidTo=x=>HIDSHOW?'':hidTop(upOf(x.id));
 const vis=m.filter(x=>!hidTo(x)),hid=m.filter(x=>hidTo(x));
 vis.forEach(x=>rows.push(fileRow(x,0,true,0,HIDSHOW&&isHid(upOf(x.id)))));
 let msg='';
 if(hid.length){
  if(!SREV)msg=`<div class=hidmsg role=button tabindex=0 data-act=revhid>${IC.eye}<span><b>${hid.length} ${hid.length===1?'track':'tracks'} found in hidden folders</b> · click to show</span></div>`;
  else{const g=new Map();for(const x of hid){const t=hidTo(x);if(!g.has(t))g.set(t,[]);g.get(t).push(x)}
   for(const [t,fs] of [...g].sort((a,b)=>a[0].toLowerCase().localeCompare(b[0].toLowerCase()))){
    const d={name:t.slice(t.lastIndexOf('/')+1),path:t,dirs:new Map(),files:[],n:fs.length};
    rows.push(folderRow(d,0,{noTog:true,count:fs.length+(fs.length===1?' match':' matches')}));
    fs.forEach(x=>rows.push(fileRow(x,1,false,0,true)))}
   msg=`<div class=hidmsg data-act=hidagain role=button tabindex=0>Hide these again</div>`}}
 return {rows,msg,none:!vis.length}}
function libHead(){
 const n=hiddenN(),b=document.getElementById('lib_hidden');
 if(!n&&HIDSHOW){HIDSHOW=false;try{localStorage.setItem('cp_lib_hidden','0')}catch(e){}}      // nothing left to show: the next folder that is hidden starts hidden
 b.hidden=!n;b.classList.toggle('on',HIDSHOW);b.setAttribute('aria-pressed',HIDSHOW);
 b.innerHTML=IC.eyeOff+`<span>${n}</span>`;
 b.title=b.ariaLabel=`Hidden folders: ${n}`}
lib_collapse.innerHTML=IC.collapse;lib_expand.innerHTML=IC.expand;
function libCollapse(all){const ps=LIBD.filter(d=>!isHid(d));if(all)for(const d of ps)closed.add(d);else for(const d of ps)closed.delete(d);saveClosed();lastLib='';renderLib()}
function libHidden(){HIDSHOW=!HIDSHOW;try{localStorage.setItem('cp_lib_hidden',HIDSHOW?'1':'0')}catch(e){}lastLib='';renderLib()}
async function flagSet(path,f){
 const cur={...flOf(path)};for(const k of Object.keys(f)){if(f[k])cur[k]=true;else delete cur[k]}
 if(Object.keys(cur).length)LIBFL[path]=cur;else delete LIBFL[path];lastLib='';renderLib();
 try{const r=await fetch('/api/library/folder/flags',{method:'POST',body:JSON.stringify({path,...f})});if(r.ok){const d=await r.json();LIBFL=d.flags||LIBFL}else{setLib(await j('/api/library'))}}catch(e){}
 lastLib='';renderLib()}
function renderLib(){
 const f=(q.value||'').toLowerCase().trim();
 if(!f)SREV=false;
 libHead();
 libcount.textContent=`(${LIBF.length})`;if(SEL.size){const have=new Set(LIBF.map(x=>x.id));let ch=false;for(const x of [...SEL])if(!have.has(x)){SEL.delete(x);ch=true}if(ch)selUi()}
 let rows=[],msg='',none=false;
 if(f){const r=searchRows(f);rows=r.rows;msg=r.msg;none=r.none}
 else{
  const root={name:'',path:'',dirs:new Map(),files:[],n:0};
  const dirOf=path=>{let n=root,cur='';if(!path)return n;for(const seg of path.split('/')){cur=cur?cur+'/'+seg:seg;
   if(!n.dirs.has(seg))n.dirs.set(seg,{name:seg,path:cur,dirs:new Map(),files:[],n:0});n=n.dirs.get(seg)}return n};
  for(const d of LIBD)dirOf(d);
  for(const x of LIBF){const i=x.id.lastIndexOf('/');dirOf(i<0?'':x.id.slice(0,i)).files.push(x)}
  const cnt=n=>{n.n=n.files.length;for(const c of n.dirs.values())n.n+=cnt(c);return n.n};cnt(root);
  const favs=favDirs(root);
  if(favs.length){
   rows.push('<div class=lsec>Favorites</div>');
   for(const d of favs){rows.push(folderRow(d,0));if(!closed.has(d.path))libRows(d,1,rows,true)}
   rows.push('<div class=lsec>All folders</div>')}
  libRows(root,0,rows,true)}
 const html=rows.length?rows.join('')+msg+`<div class="fd rootdrop" data-path="">⌂ Drop here to move to the top level of the library</div>`:(msg||'');
 const out=upRows()+(html&&!(f&&none&&!rows.length)?html:(f&&none?`<p style="opacity:.6">No tracks found</p>`+msg:(html||(UPL.length?'':`<p style="opacity:.6">${LIBF.length?'No tracks found':'The library is empty. Drop audio files here or press the upload button.'}</p>`))));
 if(out!==lastLib&&!dragging){lastLib=out;lib.innerHTML=out;markPv();selUi()}
 if(!infopop.hidden){if(LIBF.length&&!LIBF.some(x=>x.id===INF.id))infoClose();else infoPlace()}
}
function normCtl(p,i){const n=p.norm||{mode:'off'};
 const sel=`<select onchange="normSet(${i},{mode:this.value})" title="Level match: turn louder tracks down so the playlist plays at one level. It never boosts.">
  <option value=off ${n.mode==='off'?'selected':''}>Off</option><option value=track ${n.mode==='track'?'selected':''}>Match a track</option><option value=lufs ${n.mode==='lufs'?'selected':''}>Fixed LUFS</option></select>`;
 let more='';
 if(n.mode==='track')more=`<select onchange="normSet(${i},{ref:this.value})" title="The track everything else is matched to">${p.tracks.map((t,k)=>`<option value="${esc(t.id)}" ${t.id===n.ref?'selected':''}>${k}: ${esc(t.name)}</option>`).join('')}</select>`;
 else if(n.mode==='lufs')more=`<input class=nlu type=number step=0.5 min=-60 max=0 value="${n.lufs}" onchange="normSet(${i},{lufs:this.value})" aria-label="Target loudness in LUFS" title="Target loudness. -23 is broadcast, -16 to -14 is streaming"> <small>LUFS</small>`;
 return `<label class="pm lvl">Level match: ${sel}${more}</label>`}
function gainBadge(p,t){const n=p.norm||{mode:'off'};if(n.mode==='off'||t.missing)return '';
 if(n.mode==='track'&&t.id===n.ref)return `<span class="gdb ref" title="Reference track (${t.lufs} LUFS): the other tracks are matched to this">REF</span>`;
 if(!t.measured)return `<span class="gdb an" title="Analyzing loudness…">…</span>`;
 if(t.lufs===null)return `<span class=gdb title="Too short or silent to measure: played at its normal level">–</span>`;
 if(t.gain_db===null)return '';
 if(t.gain_db===0)return `<span class="gdb ok" title="${t.lufs} LUFS: already at or below the target, not changed">0 dB</span>`;
 return `<span class="gdb dn" title="${t.lufs} LUFS: turned down ${-t.gain_db} dB to match">${t.gain_db} dB</span>`}
async function normSet(i,b){await fetch('/api/playlists/'+i+'/norm',{method:'POST',body:JSON.stringify(b)});lastHtml='';render(true)}
function livePT(){const m=/^(\d+)\/(\d+)$/.exec((LASTS&&LASTS.live_id)||'');if(!m)return null;const p=PL[+m[1]];if(!p||!p.tracks[+m[2]])return null;return {i:+m[1],k:+m[2],p,t:p.tracks[+m[2]]}}
/* Show a track in its playlist: expand the playlist if it is collapsed, scroll to the row and flash it for 4 seconds. Used by the Live and Cue cards. */
function jumpToTrack(i,k){const p=PL[i],t=p&&p.tracks[k];if(!t)return;COLL.delete(p.name);try{localStorage.setItem('cp_coll',JSON.stringify([...COLL]))}catch(e){}
 PFL={i,fid:t.id,until:Date.now()+4000};lastHtml='';renderLists(LASTS);
 const el=lists.querySelector(`li.t[data-i="${i}"][data-k="${k}"]`)||lists.querySelector(`.pl[data-i="${i}"]`);
 if(el)el.scrollIntoView({block:'center',behavior:'smooth'});
 setTimeout(()=>{lastHtml='';renderLists(LASTS)},4100)}
function liveGo(){const x=livePT();if(x)jumpToTrack(x.i,x.k)}
/* confirmation after a playlist is created (Create button or the dashed drop box); clicking it shows the playlist */
let plChipT=null,plChipName='',plChipI=-1;
function plChip(msg,more){const i=PL.length-1,p=PL[i];if(!p)return;plChipName=p.name;plChipI=i;
 plchipt.textContent=msg+' “'+p.name+'”'+(more||'')+'. Click to show it';plchip.hidden=false;clearTimeout(plChipT);plChipT=setTimeout(()=>{plchip.hidden=true},12000)}
function plChipClose(e){if(e)e.stopPropagation();plchip.hidden=true;clearTimeout(plChipT)}
function plChipClick(){plChipClose();let i=PL.findIndex((p,k)=>k===plChipI&&p.name===plChipName);if(i<0)i=PL.findIndex(p=>p.name===plChipName);if(i>=0)jumpToPlaylist(i)}
function jumpToPlaylist(i){const p=PL[i];if(!p)return;COLL.delete(p.name);try{localStorage.setItem('cp_coll',JSON.stringify([...COLL]))}catch(e){}
 lastHtml='';renderLists(LASTS);const el=lists.querySelector(`.pl[data-i="${i}"]`);if(!el)return;
 el.scrollIntoView({block:'start',behavior:'smooth'});el.classList.remove('plnew');void el.offsetWidth;el.classList.add('plnew')}
function cuePT(){const m=/^(\d+)\/(\d+)$/.exec((LASTS&&LASTS.focus_id)||'');if(!m)return null;const p=PL[+m[1]];if(!p||!p.tracks[+m[2]])return null;return {i:+m[1],k:+m[2],p,t:p.tracks[+m[2]]}}
function cueGo(){const x=cuePT();if(x)jumpToTrack(x.i,x.k)}
/* a title is only a link (pointer cursor, focusable, Enter) while it has a track to go to */
function asLink(el,on,tip){el.classList.toggle('lk',on);el.title=tip;if(on){el.setAttribute('role','link');el.tabIndex=0}else{el.removeAttribute('role');el.removeAttribute('tabindex')}}
function cueSub(){const x=cuePT(),el=document.getElementById('focsub');asLink(focnm,!!x,x?'Show this track in its playlist':(LASTS.focus_name&&LASTS.focus_name!=='-'?LASTS.focus_name:''));
 if(!x){if(!el.hidden){el.hidden=true;el.innerHTML=''}return}
 const h=`<button class=lpl onclick="cueGo()" title="Show this playlist">${esc(x.p.name)}</button>`;if(el.innerHTML!==h)el.innerHTML=h;el.hidden=false}
let lastSub='';
function liveSub(){const x=livePT(),el=document.getElementById('livesub'),nm=document.getElementById('livenm');if(!el)return;
 asLink(nm,!!x,x?'Show this track in its playlist':(LASTS.live_name||''));
 if(!x){if(!el.hidden){el.hidden=true;el.innerHTML='';lastSub=''}lvClose();return}
 const n=x.p.norm||{mode:'off'};
 const g=n.mode==='off'?`<span class=gdb title="Level match is off for this playlist. Click to turn it on.">LM off</span>`:(gainBadge(x.p,x.t)||`<span class=gdb>LM</span>`);
 const h=`<button class=lpl onclick="liveGo()" title="Show this playlist">${esc(x.p.name)}</button>${eaBtn(x.i,x.k,x.t.end)}${(LASTS.live_passes||1)>1?`<span class=lpass title="This track plays twice">pass ${LASTS.live_pass} of ${LASTS.live_passes}</span>`:''}<button class=gbtn onclick="openLvl(event)" title="Level match: click to adjust" aria-label="Adjust level match">${g}</button>`;
 if(h!==lastSub){lastSub=h;el.innerHTML=h;el.hidden=false}
 if(!lvpop.hidden){lvBody();lvPlace()}}
let lvAnchor=null;
function lvBody(){const x=livePT();if(!x){lvClose();return}
 const n=x.p.norm||{mode:'off'},i=x.i;
 let step='';
 if(n.mode==='lufs')step=`<div class=stp><button class=ib onclick="lvStep(-1)" aria-label="Quieter">−</button><b>${n.lufs} LUFS</b><button class=ib onclick="lvStep(1)" aria-label="Louder">+</button></div><small>Raise the target to make quieter tracks louder. Tracks already below it are not boosted.</small>`;
 else if(n.mode==='track')step=`<small>Matched to the reference track. Pick a louder reference to raise the playlist, or switch to Fixed LUFS to nudge by steps.</small>`;
 else step=`<small>Level match is off. Pick a mode to turn louder tracks down to one level.</small>`;
 const h=`<div class=lvh><b>${esc(x.p.name)}: level match</b><button class="ib lvx" onclick="lvClose(true)" title="Close (Esc)" aria-label="Close level match">✕</button></div>${normCtl(x.p,i)}${step}`;
 if(h!==lvpop._h){lvpop._h=h;lvpop.innerHTML=h}}      // the page refreshes every second: leave the controls alone unless something changed
function lvStep(d){const x=livePT();if(!x)return;const n=x.p.norm||{};normSet(x.i,{lufs:Math.max(-60,Math.min(0,(+n.lufs||-18)+d))})}
function lvPlace(){if(lvpop.hidden)return;
 const a=lvAnchor&&lvAnchor.isConnected?lvAnchor:document.querySelector('#livesub .gbtn');if(!a)return;lvAnchor=a;
 const vv=window.visualViewport,VW=vv?vv.width:innerWidth,VH=vv?vv.height:innerHeight,OX=vv?vv.offsetLeft:0,OY=vv?vv.offsetTop:0;   // what is actually on screen (differs from the window when zoomed)
 const r=a.getBoundingClientRect(),w=lvpop.offsetWidth,h=lvpop.offsetHeight,M=8;
 lvpop.style.left=Math.max(OX+M,Math.min(r.left,OX+VW-w-M))+'px';
 const below=r.bottom+6,top=below+h<=OY+VH-M?below:r.top-6-h>=OY+M?r.top-6-h:Math.max(OY+M,OY+VH-h-M);   // below the bubble, else above it, else pinned to the bottom edge
 lvpop.style.top=top+'px'}
function lvClose(refocus){if(lvpop.hidden)return;lvpop.hidden=true;if(refocus&&lvAnchor&&lvAnchor.isConnected)lvAnchor.focus()}
function openLvl(e){e.stopPropagation();if(!lvpop.hidden){lvClose();return}
 infoClose();lvAnchor=e.currentTarget;lvBody();if(!livePT())return;lvpop.hidden=false;lvPlace()}
document.addEventListener('pointerdown',e=>{if(!lvpop.hidden&&!lvpop.contains(e.target)&&!e.target.closest('.gbtn'))lvClose()},true);   // pointerdown, so a tap closes it too
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!lvpop.hidden){lvClose(true)}});
addEventListener('resize',lvPlace);addEventListener('scroll',lvPlace,true);
/* ---- File information: the "i" on a library or playlist row. It reuses the level-match popover's behaviour (close button, Esc,
   outside pointerdown, the icon again) and is not touched by the page's re-renders. ---- */
const INFOTIP={format:'The kind of file, such as WAV or MP3.',codec:'How the sound is packed inside the file. PCM means it is not compressed.',dur:'How long the file plays.',
 bitrate:'How much data is used for each second of sound. For MP3 and similar files, higher usually means better quality.',rate:'How many times a second the sound is measured. This player works at 48,000 Hz and converts other rates when the file loads.',
 ch:'Mono is a single channel, stereo is two (left and right).',bits:'How finely each measurement is stored. 16-bit is CD quality, 24-bit is studio quality.',
 lufs:'How loud the file sounds on average over its whole length. A number closer to zero is louder (-14 is louder than -23).',tp:'The loudest point in the file. Above -1 dBTP can distort.',
 lra:'How much the loudness moves up and down through the file. A small number is steady, a large one has quiet and loud parts.',max:'The loudest single moment of the sound. 0 dB is the loudest a file can go.',
 rms:'The average level of the sound over the whole file. A lower number means quieter overall.',score:'How sure the file detector is about the format. It is not a quality score.',size:'How much disk space the file takes.'};
let INF={id:null,anchor:null,rect:null,timer:0,last:'',tip:''};
const infoAnchors=()=>[...document.querySelectorAll('[data-info]')];
function infoFind(){if(INF.anchor&&INF.anchor.isConnected)return INF.anchor;
 const pl=INF.pl?lists.querySelector(`li.t[data-i="${INF.pl[0]}"][data-k="${INF.pl[1]}"] [data-info]`):null;
 return (pl||infoAnchors().find(b=>b.dataset.info===INF.id&&!b.closest('#lists'))||null)}
function infoPlace(){if(infopop.hidden)return;
 const a=infoFind();if(a){INF.anchor=a;const r=a.getBoundingClientRect();INF.rect={left:r.left,top:r.top,bottom:r.bottom,width:r.width}}
 const r=INF.rect;if(!r)return;
 const vv=window.visualViewport,VW=vv?vv.width:innerWidth,VH=vv?vv.height:innerHeight,OX=vv?vv.offsetLeft:0,OY=vv?vv.offsetTop:0,w=infopop.offsetWidth,h=infopop.offsetHeight,M=8;
 infopop.style.left=Math.max(OX+M,Math.min(r.left+r.width/2-w/2,OX+VW-w-M))+'px';
 const below=r.bottom+6;infopop.style.top=Math.max(OY+M,Math.min(OY+VH-h-M,below+h<=OY+VH-M?below:r.top-6-h))+'px'}
function infoClose(refocus){if(infopop.hidden)return;infopop.hidden=true;clearTimeout(INF.timer);INF.id=null;INF.last='';
 if(refocus){const a=INF.anchor&&INF.anchor.isConnected?INF.anchor:null;a&&a.focus()}}
function infoVal(v,g,d,fn){return v===null||v===undefined?`<b class="nv${d.status[g]==='measuring'?' an':''}">${({'measuring':'analyzing…','needs ffmpeg':'needs ffmpeg','failed':'could not measure'})[d.status[g]]||'–'}</b>`:`<b>${fn?fn(v):esc(v)}</b>`}
const infoN=x=>x.toLocaleString('en-US'),INFOCH={1:'mono',2:'stereo'};
const infoCard=(d,k,label,g,v,fn,sub,hot)=>`<div class="ifc${hot?' hot':''}" data-k=${k} tabindex=0 title="${esc(INFOTIP[k])}"><small>${label}</small>${infoVal(v,g,d,fn)}${v!==null&&v!==undefined&&sub?`<i>${esc(sub)}</i>`:''}</div>`;
function infoBody(d){
 const n=infoN,mono=INFOCH,card=(...a)=>infoCard(d,...a);
 const cards=[
  card('format','Format','probe',d.format,null,d.format_long),
  card('codec','Codec','probe',d.codec,null,d.codec_long),
  card('dur','Duration','probe',d.dur,x=>dtxt(x),d.dur?d.dur.toFixed(2)+' s':''),
  card('bitrate','Bitrate','probe',d.bitrate,x=>n(x)+' kbps'),
  card('rate','Sample rate','probe',d.rate,x=>n(x)+' Hz'),
  card('ch','Channels','probe',d.channels,x=>x,mono[d.channels]||(d.channels?d.channels+' channels':'')),
  d.bits?card('bits','Bit depth','probe',d.bits,x=>x+'-bit'):'',
  card('lufs','LUFS','loud',d.lufs,x=>x+' LUFS'),
  card('tp','True Peak','peak',d.tp,x=>x+' dBTP'),
  card('lra','Loudness Range','peak',d.lra,x=>x+' LU'),
  card('max','Max Volume','vol',d.max,x=>x+' dB'),
  card('rms','RMS','vol',d.rms,x=>x+' dB'),
  card('score','Probe Score','probe',d.score,x=>x),
  card('size','File size','probe',d.size,x=>bytes(x))].join('');
 const fol=d.folder?d.folder:'(top level of the library)';
 return `<div class=ifh><div class=ift><b>${esc(d.name)}</b><small>${esc(fol)}</small></div><button class="ib ifx" onclick="infoClose(true)" title="Close (Esc)" aria-label="Close file information">✕</button></div>`
  +(d.error?`<div class=ifw>${esc(d.error)}</div>`:'')+(d.check?`<div class=ifw>${d.check.lv==='error'?'⛔':'⚠'} ${esc(d.check.msg)}</div>`:'')
  +`<div class=ifg>${cards}</div><div class=ifn id=ifn>${esc(INF.tip||'Hover over a value, or tap it, to see what it means.')}</div>`}
function infoShow(html){if(html===INF.last)return;const keep=infopop.scrollTop;INF.last=html;infopop.innerHTML=html;infopop.scrollTop=keep;infoPlace()}
async function infoPoll(id){clearTimeout(INF.timer);if(INF.id!==id||infopop.hidden)return;
 let d=null,err='';
 try{const r=await fetch('/api/library/info?id='+encodeURIComponent(id),{cache:'no-store'});d=await r.json();if(!r.ok)err=d.error||'could not read that file'}catch(e){err='the player did not answer'}
 if(INF.id!==id||infopop.hidden)return;
 if(err)infoShow(`<div class=ifh><div class=ift><b>${esc(id.split('/').pop())}</b></div><button class="ib ifx" onclick="infoClose(true)" title="Close (Esc)" aria-label="Close file information">✕</button></div><div class=ifw>${esc(err)}</div>`);
 else{infoShow(infoBody(d));if(!d.done)INF.timer=setTimeout(()=>infoPoll(id),1000)}
 if(err)INF.timer=setTimeout(()=>infoPoll(id),4000)}
function openInfo(id,btn){
 if(!infopop.hidden&&INF.id===id&&(!btn||INF.anchor===btn||INF.anchor&&!INF.anchor.isConnected||(INF.pl?false:!btn.closest('#lists')))){infoClose();return}   // the same icon again closes it
 lvClose();clearTimeout(INF.timer);INF.id=id;INF.anchor=btn||null;INF.last='';INF.tip='';
 const li=btn&&btn.closest('li.t');INF.pl=li?[li.dataset.i,li.dataset.k]:null;
 const r=btn?btn.getBoundingClientRect():{left:innerWidth/2,top:80,bottom:80,width:0};INF.rect={left:r.left,top:r.top,bottom:r.bottom,width:r.width};
 infopop.innerHTML=`<div class=ifh><div class=ift><b>${esc(id.split('/').pop())}</b></div><button class="ib ifx" onclick="infoClose(true)" title="Close (Esc)" aria-label="Close file information">✕</button></div><div class=ifn>Reading the file…</div>`;
 infopop.hidden=false;infoPlace();infoPoll(id)}
document.addEventListener('click',e=>{const b=e.target.closest('[data-info]');if(b)openInfo(b.dataset.info,b)});
infopop.addEventListener('click',e=>{const c=e.target.closest('.ifc');if(c){INF.tip=INFOTIP[c.dataset.k]||'';const n=document.getElementById('ifn');if(n)n.textContent=INF.tip;infopop.querySelectorAll('.ifc').forEach(x=>x.classList.toggle('sel',x===c));INF.last=''}});   // (a tap shows the meaning where there is no hover)
infopop.addEventListener('focusin',e=>{const c=e.target.closest&&e.target.closest('.ifc');if(c){INF.tip=INFOTIP[c.dataset.k]||'';const n=document.getElementById('ifn');if(n)n.textContent=INF.tip}});
document.addEventListener('pointerdown',e=>{if(!infopop.hidden&&!infopop.contains(e.target)&&!e.target.closest('[data-info]'))infoClose()},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!infopop.hidden){infoClose(true)}});
/* Hint popover (2.7.5 input-arm-font-hint): a small info button with data-hint opens #hintpop beside it (click, Enter or Space, so it works on touch too). It closes on Escape (focus
   goes back to the button), on a click outside, when the button is clicked again, and when the button is hidden. It is kept inside the visible viewport. */
const HINT={b:null};
function hintPlace(){
 const b=HINT.b;if(!b||hintpop.hidden)return;
 if(!b.isConnected||!b.getClientRects().length){hintClose();return}
 const r=b.getBoundingClientRect(),vv=window.visualViewport,VW=vv?vv.width:innerWidth,VH=vv?vv.height:innerHeight,OX=vv?vv.offsetLeft:0,OY=vv?vv.offsetTop:0,w=hintpop.offsetWidth,h=hintpop.offsetHeight,M=8;
 hintpop.style.left=Math.max(OX+M,Math.min(r.left+r.width/2-w/2,OX+VW-w-M))+'px';
 const below=r.bottom+6;hintpop.style.top=Math.max(OY+M,Math.min(OY+VH-h-M,below+h<=OY+VH-M?below:r.top-6-h))+'px'}
function hintClose(refocus){const b=HINT.b;if(hintpop.hidden&&!b)return;hintpop.hidden=true;HINT.b=null;if(b){b.setAttribute('aria-expanded','false');if(refocus&&b.isConnected)b.focus({preventScroll:true})}}
function hintOpen(b){hintClose();HINT.b=b;hintpop.textContent=b.dataset.hint;hintpop.hidden=false;b.setAttribute('aria-expanded','true');hintPlace()}
document.addEventListener('click',e=>{const b=e.target.closest('[data-hint]');if(!b)return;e.preventDefault();if(HINT.b===b)hintClose();else hintOpen(b)});
document.addEventListener('pointerdown',e=>{if(HINT.b&&!hintpop.contains(e.target)&&!e.target.closest('[data-hint]'))hintClose()},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&HINT.b){e.stopPropagation();hintClose(true)}},true);
window.addEventListener('resize',hintPlace);window.addEventListener('scroll',hintPlace,true);
if(window.visualViewport)visualViewport.addEventListener('resize',hintPlace);
addEventListener('resize',infoPlace);addEventListener('scroll',infoPlace,true);
/* ---- File information strip in the Preview panel: one fetch per previewed file from the same /api/library/info (and cache) as
   the popup, polled only while the player is still measuring. Collapsed = one line, expanded = the cards; docked under a playlist row = a compact line. ---- */
let PVF={id:null,d:null,tries:0,timer:0,open:false,html:''};
try{PVF.open=localStorage.getItem('cp_pvinfo')==='1'}catch(e){}
function pvInfoSync(){const id=PVCUR.id||null;if(id===PVF.id)return;
 clearTimeout(PVF.timer);PVF.id=id;PVF.d=null;PVF.err=false;PVF.tries=0;if(id)pvInfoFetch(id);pvInfoRender()}
async function pvInfoFetch(id){clearTimeout(PVF.timer);if(PVF.id!==id)return;
 let d=null;try{const r=await fetch('/api/library/info?id='+encodeURIComponent(id),{cache:'no-store'});if(r.ok)d=await r.json()}catch(e){}
 if(PVF.id!==id)return;
 if(d){PVF.d=d;PVF.tries=0;PVF.err=false;if(!d.done)PVF.timer=setTimeout(()=>pvInfoFetch(id),1500)}
 else{PVF.err=true;if(++PVF.tries<=3)PVF.timer=setTimeout(()=>pvInfoFetch(id),4000)}      // quietly: nothing is shown for a file that cannot be read
 pvInfoRender()}
function pvInfoToggle(){PVF.open=!PVF.open;try{localStorage.setItem('cp_pvinfo',PVF.open?'1':'0')}catch(e){}pvInfoRender()}
function pvInfoChips(d,docked){
 const st=d.status||{},ms=g=>st[g]==='measuring',chips=[],add=(h,cls)=>chips.push(`<span class="pvi-c${cls?' '+cls:''}">${h}</span>`);
 const kHz=r=>(+(r/1000).toFixed(1))+' kHz',ch=d.channels?(INFOCH[d.channels]||d.channels+' ch'):'',cap=x=>x.charAt(0).toUpperCase()+x.slice(1);
 const fmt=d.format?d.format.toLowerCase():'';
 if(docked){const a=[fmt,d.bitrate?infoN(d.bitrate)+' kbps':''].filter(Boolean).join(' ');if(a)add(esc(a))}
 else{if(d.dur)add(dtxt(d.dur));if(fmt)add(esc(fmt));if(d.bitrate)add(infoN(d.bitrate)+' kbps')}
 if(d.rate)add(kHz(d.rate));if(ch)add(cap(ch));
 if(d.lufs!=null)add(d.lufs+' LUFS','pvi-l');else if(ms('loud'))add('LUFS analyzing…','nv an');
 const pk=d.tp!=null?d.tp:d.max,pkl=d.tp!=null?'dB peak':'dB max';
 if(pk!=null)add(pk+' '+pkl,pk>-1?'pvi-hot':'');else if(ms(d.tp==null&&ms('peak')?'peak':'vol'))add('peak analyzing…','nv an');
 if(docked&&d.lra!=null)add(d.lra+' LU range');
 if(!chips.length&&(ms('probe')||ms('loud')))add('analyzing…','nv an');
 return chips}
function pvInfoRender(){const el=document.getElementById('pvinfo');if(!el)return;
 if(!PVF.id||(PVF.err&&!PVF.d)){if(!el.hidden){el.hidden=true;el.innerHTML='';PVF.html=''}return}
 const d=PVF.d,docked=pv.classList.contains('docked'),ic=`<span class=pvi-i title="File information" aria-hidden=true>${IC.info}</span>`;
 let h;
 if(!d)h=`<div class=pvi-row>${ic}<span class="pvi-c nv">Reading file information…</span></div>`;
 else if(docked)h=`<div class=pvi-row>${ic}${pvInfoChips(d,true).join('<span class=pvi-s>·</span>')}<button class=lnk data-info="${esc(PVF.id)}" title="Open the full file information">All details…</button></div>`;
 else if(!PVF.open)h=`<div class=pvi-row>${ic}${pvInfoChips(d,false).join('<span class=pvi-s>·</span>')}<button class=lnk onclick="pvInfoToggle()" aria-expanded=false title="Show every value">More</button></div>`;
 else{const c=(...a)=>infoCard(d,...a),hot=v=>v!=null&&v>-1;
  h=`<div class=pvi-row><b class=pvi-t>${ic} File information</b><button class=lnk onclick="pvInfoToggle()" aria-expanded=true title="Show the short line">Hide</button></div><div class=ifg>`
   +[c('format','Format','probe',d.format,null,d.format_long),c('codec','Codec','probe',d.codec,null,d.codec_long),c('dur','Duration','probe',d.dur,x=>dtxt(x),d.dur?d.dur.toFixed(2)+' s':''),
    c('bitrate','Bitrate','probe',d.bitrate,x=>infoN(x)+' kbps'),c('rate','Sample rate','probe',d.rate,x=>infoN(x)+' Hz'),c('ch','Channels','probe',d.channels,x=>x,INFOCH[d.channels]||(d.channels?d.channels+' channels':'')),
    c('lufs','LUFS','loud',d.lufs,x=>x+' LUFS'),c('tp','True Peak','peak',d.tp,x=>x+' dBTP',null,hot(d.tp)),c('lra','Loudness Range','peak',d.lra,x=>x+' LU'),
    c('max','Max Volume','vol',d.max,x=>x+' dB',null,hot(d.max)),c('rms','RMS','vol',d.rms,x=>x+' dB')].join('')+'</div>'}
 h=`<div class="pvi${docked?' dk':''}${PVF.open&&!docked&&d?' open':''}">${h}</div>`;
 if(h!==PVF.html){PVF.html=h;el.innerHTML=h}el.hidden=false}
function plPlayBtn(p,i){
 const shuf=p.mode==='shuffle',ok=p.tracks.some(t=>!t.missing),lab=shuf?'Shuffle':'Play';
 const tip=!p.tracks.length?'This playlist is empty':!ok?'All tracks in this playlist are missing':shuf?'Play this playlist shuffled':'Play this playlist live';
 return `<button class="go plplay" onclick="cmd('${i}/play')" title="${tip}" aria-label="${tip}"${ok?'':' disabled'}>${shuf?IC.shuf:IC.cplay}<span>${lab}</span></button>`}
let LASTS={};
function renderLists(s){
 LASTS=s;PGD={};
 const html=!PL.length?'<div class=emptydrop>No playlists yet.<br>Drag a track here from the library (or drop audio files) to start one.</div>':PL.map((p,i)=>`<div class="pl${isColl(p)?' coll':''}" data-i=${i}><div class=plh><button class=plcol onclick="togglePl(${i})" title="${isColl(p)?'Expand':'Collapse'} this playlist" aria-label="${isColl(p)?'Expand':'Collapse'} this playlist" aria-expanded="${!isColl(p)}"><svg width=14 height=14 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=3 stroke-linecap=round stroke-linejoin=round><path d="M6 9l6 6 6-6"/></svg></button><span class=plgrip draggable=true title="Drag to reorder the playlists">⠿</span>
  <b class=pln title="Playlist ${i}. Double-click to rename" ondblclick="renamePl(${i})">${esc(p.name)}<span class=plc>${p.tracks.length} track${p.tracks.length===1?'':'s'}</span></b>
  ${plPlayBtn(p,i)}<button class=plren onclick="renamePl(${i})" title="Rename this playlist" aria-label="Rename this playlist"><svg width=15 height=15 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg></button>
  <button class="del plbin" onclick="delpl(${i})" title="Delete this playlist (tracks stay in the library)" aria-label="Delete this playlist"><svg width=15 height=15 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg></button>
  ${plProgHtml(p,i)}
  <div class=plopt><label class=pm title="What happens when a track in this playlist ends. To repeat or stop at one track, use that track's end-action button.">Playlist behavior: <select onchange="cmd('${i}/mode/'+this.value)">${MODES.map(([v,l])=>`<option value=${v} ${p.mode===v?'selected':''}>${l}</option>`).join('')}</select></label>
  ${normCtl(p,i)}</div></div>
  <ol>${p.tracks.map((t,k)=>{const live=s.live_id==i+'/'+k;return `<li class="t ${pvKey===i+'/'+k?'pvx':''} ${t.missing?'miss':''} ${PFL.fid===t.id&&PFL.i===i&&Date.now()<PFL.until?'flash':''} ${s.live_id==i+'/'+k?'live':''} ${s.focus_id==i+'/'+k?'focus':''} ${plDone(i,s).has(k)?'done':''}" draggable=${pvKey===i+'/'+k?'false':'true'} data-i=${i} data-k=${k} data-fid="${esc(t.id)}">
  <span class=flag ${folderColor(t.id)?`style="--fc:${folderColor(t.id)}"`:''} title="${esc(t.id.includes('/')?t.id.slice(0,t.id.lastIndexOf('/')):'(top level of the library)')}. Click to find the track in the library."></span>
  <span class=grip title="Drag to reorder, or onto another playlist">⠿</span>
  <code class=ix>/${i}/${k}</code> ${ramDot(t)}${s.live_id==i+'/'+k?'<span class=tnw>':''}<span class="tn${t.name.length>30?' lg':''}" title="${esc(t.name)}">${esc(t.name)}${t.missing?' <small>(file missing)</small>':''}</span>${s.live_id==i+'/'+k?`<span class=tsub><span class=rpe></span>${rowBadges(i,k,t,1)}</span></span>`+gainBadge(p,t):gainBadge(p,t)}${live?'':rowBadges(i,k,t)}<span class="sz tdur"${tmx(t)&&!live?' hidden':''}>${LIBDUR[t.id]?dtxt(LIBDUR[t.id]):''}</span>
  <span class=acts><button class="ib inf" data-info="${esc(t.id)}" title="File information" aria-label="File information">${IC.info}</button><button class="ib pv" data-ic=play onclick="pvPlay({p:${i},t:${k}})" title="Preview this track (PVW)">${IC.play}</button><button class="pri go" onclick="cmd('${i}/${k}')" title="Go: play this track now">Go</button>${eaBtn(i,k,t.end)}<button class="ib tr${tmx(t)?' on':''}" onclick="openTrim(${i},${k})" title="${tmx(t)?'Trimmed: '+trimTxt(tmx(t))+'. Click to edit the A and B points.':'Set A and B points: play only part of this track'}" aria-label="Set A and B points">${IC.trim}</button><button class="ib xf" onclick="cmd('${i}/${k}/xfade')" title="Crossfade to this track" aria-label="Crossfade to this track"><svg width=18 height=14 viewBox="0 0 24 18" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round><path d="M2 3h5c6 0 8 12 15 12"/><path d="M2 15h5c6 0 8-12 15-12"/></svg></button>
  <button class="ib del" onclick="rm(${i},${k})" title="Remove from this playlist (the file stays in the library)">✕</button></span>${pvKey===i+'/'+k?'<div class=pvslot></div>':''}${s.live_id==i+'/'+k?'<i class=rpl><b></b></i>':''}</li>`}).join('')}</ol>
  ${p.tracks.length?'':'<div class=hint>Drag tracks here from the library, or drop audio files</div>'}</div>`).join('');
 if(html!==lastHtml&&!dragging&&!pvSeeking&&!(document.activeElement&&(document.activeElement.classList.contains('pn')||document.activeElement.classList.contains('nlu')))){pvHome();lastHtml=html;lists.innerHTML=html;markPv();fitSub()}
 plProgTick(true);pvDock()}
/* Playing row (2.7.4 rc2): the trim, trigger and crossfade badges sit on the second line next to the elapsed text; they stay in the normal place on the other rows.
   rowBadges(.., 1) wraps each in .bw (display:contents) so fitSub() can hide the least important first (trigger, trim, crossfade) when the line is too short. */
function xfBadge(t){return t.xfade!=null?`<span class=trb title="Own crossfade time: ${t.xfade/1000} s when crossfading into this track (the master time is not used)">XF ${t.xfade/1000}s</span>`:''}
function rowBadges(i,k,t,wrap){const a=[['trim',trimBadge(i,k,t)],['trg',trgBadge(i,k,t)],['xf',xfBadge(t)]];
 return wrap?a.map(([n,h])=>h?`<span class="bw bw-${n}">${h}</span>`:'').join(''):a.map(x=>x[1]).join('')}
function fitSub(){const li=document.querySelector('#lists li.t.live'),sub=li&&li.querySelector('.tsub');if(!sub||!sub.clientWidth)return;
 const ws=[...sub.querySelectorAll('.bw')];ws.forEach(w=>w.hidden=false);
 const order=['trg','trim','xf'],gone=[];
 for(const n of order){if(sub.scrollWidth<=sub.clientWidth+0.5)break;const w=sub.querySelector('.bw-'+n);if(w){w.hidden=true;gone.push(n)}}
 const all=ws.map(w=>{const b=w.firstElementChild;return (b&&(b.getAttribute('aria-label')||b.title)||'')}).filter(Boolean).join(' | ');
 if(gone.length){li.title=all;li.setAttribute('aria-label',all)}else{li.removeAttribute('title');li.removeAttribute('aria-label')}}
addEventListener('resize',()=>fitSub());
function memShow(m){
 if(!m||!m.ram_total)return;
 const G=1073741824,M=1048576,rp=m.ram_used/m.ram_total,cp=m.cache_budget?m.cache/m.cache_budget:0;
 mem_ram.textContent=Math.round(rp*100)+'%';mem_ramx.textContent=' ('+(m.ram_used/G).toFixed(1)+' GB\u00a0/ '+(m.ram_total/G).toFixed(0)+' GB)';
 const fm=b=>b>=G?(b/G).toFixed(1)+' GB':Math.round(b/M)+' MB',u=b=>b>=G?'GB':'MB',nu=b=>b>=G?(b/G).toFixed(1):Math.round(b/M);
 mem_cache.textContent=fm(m.cache)+' / '+fm(m.cache_budget);
 mem_cache_s.textContent=u(m.cache)===u(m.cache_budget)?nu(m.cache)+' / '+fm(m.cache_budget):mem_cache.textContent;
 memro.className='memro'+(rp>.92?' bad':rp>.8?' warn':'');
 memro.title='Whole machine: '+(m.ram_used/G).toFixed(1)+' of '+(m.ram_total/G).toFixed(1)+' GB in use\nThis player: '+Math.round(m.proc/M)+' MB\nDecoded-track cache: '+fm(m.cache)+' of '+fm(m.cache_budget)+' budget ('+m.cache_tracks+' tracks)'+(cp>.9?'\nThe cache is nearly full: the least recently used tracks are dropped first.':'');
}
/* ---- Health: the dot, the panel behind it, and Settings > System > Health and alerts (2.8.0) ---- */
const HNAME={starting:'Starting',ready:'Ready',degraded:'Degraded',problem:'Problem'};
const HSTAT={ok:'OK',warn:'Warning',bad:'Problem',unknown:'Not known yet'};
const HICO={ok:'<circle cx=12 cy=12 r=10 /><path d="m9 12 2 2 4-4"/>',warn:'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
 bad:'<path d="m15 9-6 6"/><path d="M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z"/><path d="m9 9 6 6"/>',
 unknown:'<circle cx=12 cy=12 r=10 /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>'};
var HLAST=null,HOPEN=false;
function healthSync(h){
 h=h||{status:'error',detail:''};
 const st=h.state||(h.status==='error'?'problem':(h.status||'starting'));
 const sum=h.summary||(st==='problem'?h.detail:'')||'';
 HLAST={...h,st,sum};
 hdot.dataset.h=st;
 hdot.title='Health: '+(HNAME[st]||st)+(sum?'. '+sum:'')+'. Click for details.';
 hdot.setAttribute('aria-label','Health: '+(st==='starting'?'starting':(HNAME[st]||st).toLowerCase())+(sum?'. '+sum:''));
 if(HOPEN)hpRender()}
function hpRender(){
 const h=HLAST;if(!h)return;
 hp_state.textContent=HNAME[h.st]||h.st;hp_state.dataset.h=h.st;
 const rows=(h.checks&&h.checks.length?h.checks:[{id:'x',status:h.st==='problem'?'bad':'ok',title:'Player',text:h.sum||''}]);
 hp_list.innerHTML=rows.map(c=>{const up=c.id==='uptime';
  return `<li data-s="${c.status}" data-id="${c.id}"><svg aria-hidden=true viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round>${HICO[c.status]||HICO.unknown}</svg><div class=hpt><span>${esc(c.title)}<span class=vh>: ${HSTAT[c.status]||c.status}</span></span>${up?`<span class=hpv>${esc(c.text)}</span>`:''}</div>${!up&&c.status!=='ok'&&c.text?`<div class=hpx2>${esc(c.text)}</div>`:''}${c.note?`<div class="hpx2 hpn">${esc(c.note)}</div>`:''}</li>`}).join('');
 const pe=h.push_error;hp_push.hidden=!pe;hp_push.textContent=pe?'Last push failed: '+pe:''}
function hpPlace(){const r=hdot.getBoundingClientRect();hpop.style.setProperty('--hx',Math.max(8,Math.min(r.left-4,innerWidth-hpop.offsetWidth-8))+'px');hpop.style.setProperty('--hy',(r.bottom+8)+'px')}
function hpOpen(){HOPEN=true;hpRender();hpop.hidden=false;hdot.setAttribute('aria-expanded','true');hp_msg.textContent='';hpPlace();hpop.focus({preventScroll:true})}
function hpClose(refocus){if(!HOPEN)return;HOPEN=false;hpop.hidden=true;hdot.setAttribute('aria-expanded','false');if(refocus)hdot.focus()}
function hpTog(){HOPEN?hpClose(true):hpOpen()}
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&HOPEN&&!document.querySelector('dialog[open]')){e.preventDefault();e.stopPropagation();hpClose(true)}},true);
document.addEventListener('pointerdown',e=>{if(HOPEN&&!e.target.closest('#hpop,#hdot'))hpClose(false)},true);
addEventListener('resize',()=>{if(HOPEN)hpPlace()});
async function hpCopy(){
 let t='';
 try{t=(await j('/api/health/report')).text}catch(e){hp_msg.textContent='Could not build the report.';return}
 let ok=false;
 try{await navigator.clipboard.writeText(t);ok=true}catch(e){
  try{const a=document.createElement('textarea');a.value=t;a.style.cssText='position:fixed;left:-9999px;top:0';document.body.appendChild(a);a.select();ok=document.execCommand('copy');a.remove();hp_copy.focus()}catch(e2){}}
 hp_msg.textContent=ok?'Report copied.':'Could not copy. Select the text from /api/health/report instead.'}
/* Settings > System > Health and alerts: every control saves as you change it */
var HS=null,HSBUSY=false;
async function hsLoad(){try{hsShow(await j('/api/settings/health'))}catch(e){}}
function hsShow(r){
 HS=r;const p=r.push||{};
 set_pname.value=r.player_name||'';hs_name.textContent='Messages are sent as: '+(r.player_in_use||'');set_wd.checked=!!r.watchdog;set_pva.checked=!!r.preview_amber;set_push.checked=!!p.enabled;set_pushhold.checked=!!p.hold;
 for(const k of ['problem','recovered','degraded_long','watchdog'])document.getElementById('set_ev_'+k).checked=!(p.events&&p.events[k]===false);
 set_pushurl.value='';set_pushurl.placeholder=p.has_url?'Saved. Type a new one to replace it.':'https://';
 hs_clear.hidden=!p.has_url;hs_host.textContent=p.has_url?'Messages go to '+p.host+' (the rest of the address is kept private).':'No address yet. Messages need one; n8n, Slack and Discord webhooks work.';
 hs_err.textContent=p.last_error?'Last push failed: '+p.last_error:'';hs_err.className='hint2'+(p.last_error?' bad':'');
 setSums()}
async function hsPost(body){
 try{const r=await fetch('/api/settings/health',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();
  if(!r.ok||!d.ok){say(d.error||'Could not save.',false);await hsLoad();return false}
  say('Saved.',true);hsShow(d);return true}catch(e){say('Could not reach the player.',false);return false}}
function hsSave(o){return hsPost(o)}
function hsName(){return hsPost({player_name:set_pname.value})}
function hsPush(o){return hsPost({push:o})}
function hsEvents(){const ev={};for(const k of ['problem','recovered','degraded_long','watchdog'])ev[k]=document.getElementById('set_ev_'+k).checked;return hsPush({events:ev})}
async function hsUrlSave(){
 const v=set_pushurl.value.trim();if(!v)return;
 if(!/^https?:\/\/[^\s\/]+/i.test(v)){say('The address must start with http:// or https://',false);set_pushurl.classList.add('bad');return}
 set_pushurl.classList.remove('bad');await hsPush({url:v})}
function hsUrlClear(){set_pushurl.value='';return hsPush({url:'',enabled:false})}
async function hsTest(){
 hs_test.disabled=true;hs_chip.hidden=false;hs_chip.className='chipb';hs_chip.textContent='Sending…';
 try{const r=await fetch('/api/settings/health/push-test',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const d=await r.json();
  const t=new Date((d.at||Date.now()/1000)*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  hs_chip.className='chipb '+(d.ok?'ok':'bad');hs_chip.textContent=d.ok?'Sent '+t:d.error||'Failed'}
 catch(e){hs_chip.className='chipb bad';hs_chip.textContent='Could not reach the player'}
 hs_test.disabled=false;await hsLoad()}
async function render(force){
 const s=await j('/api/state');memShow(s.mem);ramShow(s.ram);
 const idle=s.live_id==='-'||s.state==='stopped'||s.state==='idle';
 cl.classList.toggle('idle',idle);stpill.textContent=s.on_top==='1'&&s.state==='playing'?'ON TOP':s.state.toUpperCase();stpill.className='pill '+s.state.toUpperCase();
 healthSync(s.health);
 if(s.version)appver.textContent='Cue Media Engine '+s.version;pfxSync(s.variable_prefix);mstripSync(s);wnSync(s.warning);remv.textContent=s.remaining;wnApply(s.remaining);{const tl=(s.live_out||0)-(s.live_in||0);ldurv.textContent=s.live_dur?'of '+mmss(tl>0.5&&tl<s.live_dur-0.5?tl:s.live_dur)+(tl>0.5&&tl<s.live_dur-0.5?' (trimmed)':' total'):''}TRFADE=s.trim_fade_ms||1500;TRFADEIN=s.trim_fadein_ms||0;
 if(window.dk_thr&&!potrow.contains(document.activeElement)&&Date.now()-dkTouch>1500){dk_thr.value=s.duck_threshold;dk_rat.value=s.duck_ratio;dk_att.value=s.duck_attack;dk_rel.value=s.duck_release;top_trk.value=s.top_level;dk_hold.checked=s.duck_hold==='1';dkInfo()}if(s.input)inpSync(s.input);LASTS=s;liveSub();livenm.textContent=s.live_name;livenm.title=s.live_name;
 focid.textContent='['+s.focus_id+']';focnm.textContent=s.focus_name==='-'?'No cue':s.focus_name;focnm.classList.toggle('dim',s.focus_name==='-');LASTS=s;cueSub();updFocTrim();updFocXf();cueIn();
 if(Date.now()-volTouch>1500){livevol.value=s.live_volume;livevolv.textContent=s.live_volume+'%'}
 mutebtn.classList.toggle('muted',+s.live_volume===0);mutebtn.setAttribute('aria-pressed',+s.live_volume===0);if(s.go_transition)goSync(s.go_transition);ppbtn.innerHTML=s.state==='paused'?LI.play:LI.pause;ppbtn.title=s.state==='paused'?'Resume':'Pause';
 prepmsg.textContent=GOLOAD?GOHINT:s.loading!=='-'?'Preparing "'+s.loading+'"…':'';
 LIVE={fid:s.live_fid,pos:s.live_pos,dur:s.live_dur,lo:s.live_in||0,hi:s.live_out||s.live_dur,playing:s.state==='playing'||s.state==='fading',t0:performance.now()};trgSync(s);
 {const lp=/^(\d+)\//.exec(s.live_id||''),lsh=lp&&PL[+lp[1]]&&PL[+lp[1]].mode==='shuffle'&&s.live_id!==lastLiveId;lastLiveId=s.live_id;
  if(s.rev===lastRev&&!force&&(lsh||s.ram&&s.ram.rev!==lastRamRev)){PL=await j('/api/playlists');lastRamRev=s.ram?s.ram.rev:lastRamRev;cueSub();updFocXf()}}   // only the RAM states changed: refetch the lists, not the library
 if(s.rev!==lastRev||force){
  const [pl,lb,sc]=await Promise.all([j('/api/playlists'),j('/api/library'),j('/api/scan')]);
  lastRev=s.rev;lastRamRev=s.ram?s.ram.rev:lastRamRev;PL=pl;cueSub();updFocTrim();updFocXf();setLib(lb);STORE=lb.storage;SCAN=sc;lastStore=Date.now();
  renderStore();renderScan();renderLib();
 }else if(Date.now()-lastStore>10000){STORE=await j('/api/storage');lastStore=Date.now();renderStore()}
 LASTSOLO=!!s.preview.solo;soloUi(s);
 if(s.preview.device!==PVDEV){PVDEV=s.preview.device;lastLib='';renderLib();lastHtml='';fillPvTarget()}
 renderPv(s.preview);
 renderLists(s);
}
let LIBDUR={},durT=null,fmtTries=0;
const dtxt=x=>{x=Math.round(x);return x>=3600?Math.floor(x/3600)+':'+String(Math.floor(x%3600/60)).padStart(2,'0')+':'+String(x%60).padStart(2,'0'):Math.floor(x/60)+':'+String(x%60).padStart(2,'0')};
function setLib(lb){LIBF=lb.files;LIBD=lb.folders||[];LIBC=lb.colors||{};LIBI=lb.icons||{};LIBFL=lb.flags||{};LIBDUR={};let miss=false;
 for(const f of LIBF){if(f.dur==null)miss=true;else LIBDUR[f.id]=f.dur;if(f.fmt==null&&fmtTries<20)miss=true}
 if(miss&&!durT)durT=setTimeout(async()=>{durT=null;fmtTries++;try{setLib(await j('/api/library'));lastLib='';lastHtml='';renderLib();render(false)}catch(e){}},2000)}
const mmss=x=>{x=Math.max(0,Math.round(x));return String(Math.floor(x/60)).padStart(2,'0')+':'+String(x%60).padStart(2,'0')};
function renderPv(v){
 if(pvt()==='browser'){renderLocal();return}
 pvlbl.textContent=pvt()==='both'?'- browser + player output':'- player output';
 pv.classList.toggle('on',!!v.device);pvState=v.state;
 if(typeof v.muted==='boolean'&&v.muted!==pvMuted){pvMuted=v.muted;pvMuteUi()}
 PVCUR={id:(v.state==='stopped'||v.state==='error')?null:v.fid,state:v.state};markPv();
 PVST={pos:v.pos||0,dur:v.dur||0,state:v.state,t0:performance.now()};
 if(!v.device)return;
 pvname.textContent=(v.state==='stopped'||v.state==='error')?'-':v.name+(v.state==='loading'?' (loading…)':'');
 setPP(v.state==='paused');
 if(!pvSeeking){pvseek.max=v.dur||1;pvseek.value=v.pos}
 pvtime.textContent=mmss(v.pos)+' / '+mmss(v.dur);
 if(document.activeElement!==pvvol)pvvol.value=v.volume;
 pverr.textContent=v.state==='error'?v.error:'';
}
/* ---- preview: either the player's own second output ('pi') or this browser ('browser') ---- */
const pvt=()=>{let v=null;try{v=localStorage.getItem('cp_pvtarget')}catch(e){}
 if((v==='pi'||v==='both')&&PVDEV)return v;if(v==='browser')return 'browser';return PVDEV&&!matchMedia('(max-width:34rem)').matches?'pi':'browser'};      // no choice made yet: a phone plays the preview on the phone
const AU=new Audio();AU.preload='auto';let lp=null,AC=null,AN=[null,null],lpk=[0,0],lastLoc='';
function setupMeter(){
 if(AC)return;try{AC=new (window.AudioContext||window.webkitAudioContext)();
  const src=AC.createMediaElementSource(AU),up=AC.createGain();
  up.channelCount=2;up.channelCountMode='explicit';up.channelInterpretation='speakers';   // mono plays on both sides
  const sp=AC.createChannelSplitter(2);src.connect(up);up.connect(AC.destination);up.connect(sp);
  AN=[0,1].map(c=>{const a=AC.createAnalyser();a.fftSize=1024;sp.connect(a,c);return a})}catch(e){AC=null}}
const MST=/*MST*/[];      // the console taper, generated from METER_STOPS in player.py
function meterPct(db){if(db>=0)return 100;for(let i=0;i<MST.length-1;i++){const [d1,p1]=MST[i],[d2,p2]=MST[i+1];if(db>=d2)return p2+(p1-p2)*(db-d2)/(d1-d2)}return 0}
function soloLevels(m){const g=20*Math.log10(Math.max(.001,+pvvol.value));return ['l_db','r_db'].map(k=>m.live?meterPct(Math.max(-90,m.live[k]+g)):0)}   // Solo live in this browser: the live level at the preview volume
function localLevels(){
 const out=[0,0];
 if(AN[0]&&lp&&!AU.paused){const b=new Float32Array(1024);
  for(let c=0;c<2;c++){AN[c].getFloatTimeDomainData(b);let pk=0;for(let i=0;i<b.length;i++){const x=Math.abs(b[i]);if(x>pk)pk=x}
   out[c]=pk>0?meterPct(20*Math.log10(pk)):0}}
 for(let c=0;c<2;c++){lpk[c]=Math.max(out[c],lpk[c]-3.5);out[c]=lpk[c]}   // fall back at about 30 dB/s like the live meters
 return out}
function renderLocal(){
 if(pvt()==='both')return;
 pv.classList.add('on');pvlbl.textContent='- this browser';
 const st=!lp?'stopped':AU.error?'error':AU.ended?'stopped':AU.paused?'paused':'playing';pvState=st;
 PVCUR={id:st==='stopped'||st==='error'?null:lp.id,state:st};markPv();
 pvname.textContent=lp&&st!=='stopped'?lp.name+(AU.readyState<3&&st==='playing'?' (loading…)':''):'-';
 setPP(st==='paused');
 const dur=isFinite(AU.duration)?AU.duration:0;
 if(!pvSeeking){pvseek.max=dur||1;pvseek.value=st==='stopped'?0:AU.currentTime}
 pvtime.textContent=mmss(st==='stopped'?0:AU.currentTime)+' / '+mmss(dur);
 if(document.activeElement!==pvvol)pvvol.value=AU.volume;
 pverr.textContent=st==='error'?'this browser could not play that file':''}
['timeupdate','play','pause','ended','loadedmetadata','error','waiting','playing'].forEach(e=>AU.addEventListener(e,()=>{if(pvt()==='browser')renderLocal()}));
function localPlay(id,name){
 setupMeter();if(AC&&AC.state==='suspended')AC.resume();
 lp={id,name};AU.src='/api/library/file?id='+encodeURIComponent(id);AU.play().catch(()=>{});renderLocal()}
function localCtl(c,x){
 if(c==='stop'){AU.pause();lp=null;AU.removeAttribute('src');AU.load()}
 else if(c==='pause')AU.pause();else if(c==='resume'){if(AC&&AC.state==='suspended')AC.resume();AU.play().catch(()=>{})}
 else if(c==='seek'&&isFinite(AU.duration))AU.currentTime=x.pos;
 else if(c==='vol')AU.volume=Math.max(0,Math.min(1,x.v));
 renderLocal()}
/* "Both": the player's output is the master and this browser follows it, so the two stay together (within a fraction of a second) */
let bothT=0,bothC=0;
function bothStart(id,name){bothT=Date.now();const f=LIBF.find(x=>x.id===id);
 lp={id,name:name||(f?f.name:String(id).replace(/\.[^.]+$/,'').split('/').pop())};AU.src='/api/library/file?id='+encodeURIComponent(id);
 AU.muted=true;AU.play().then(()=>{AU.pause();AU.muted=false}).catch(()=>{AU.muted=false})}   // unlock playback now, start it when the player does
function bothStop(){AU.pause();lp=null;AU.removeAttribute('src');AU.load()}
function bothSync(v){
 if(Date.now()-bothC<700)return;      // just after you pressed a control: ignore polls that predate it
 const st=v.state;if(AC&&AC.state==='suspended')AC.resume();
 if(st==='stopped'||st==='error'){if(lp&&Date.now()-bothT>4000)bothStop();return}
 if(PVCUR.id&&(!lp||lp.id!==PVCUR.id))bothStart(PVCUR.id);
 if(!lp||AU.error)return;
 if(st==='playing'){if(AU.paused&&AU.readyState>=2)AU.play().catch(()=>{});
  if(isFinite(AU.duration)&&Math.abs(AU.currentTime-v.pos)>0.5)AU.currentTime=v.pos}
 else if(!AU.paused)AU.pause()}
async function pvPoll(){if(!PVDEV||pvt()==='browser')return;try{const v=await j('/api/preview');renderPv(v);if(pvt()==='both')bothSync(v)}catch(e){}}
async function pvPlay(b){
 const id=b.id!==undefined?b.id:(PL[b.p]&&PL[b.p].tracks[b.t]||{}).id;if(id===undefined)return;
 PVTRIM=b.id!==undefined?null:(tmx(PL[b.p].tracks[b.t])||null);PVROW=b.id!==undefined?null:{p:b.p,t:b.t};
 if(PVCUR.id===id&&['playing','loading','paused'].includes(PVCUR.state)){pvCtl(PVCUR.state==='paused'?'resume':'pause');return}   // same track: pause / resume
 if(pvt()==='browser'){const f=LIBF.find(x=>x.id===id);localPlay(id,f?f.name:id.replace(/\.[^.]+$/,'').split('/').pop());return}
 if(pvt()==='both')bothStart(id);
 await fetch('/api/preview/play',{method:'POST',body:JSON.stringify(b)});pvPoll()}
async function pvCtl(c,extra){
 if(pvt()==='browser'){localCtl(c,extra||{});return}
 if(pvt()==='both'){if(c!=='vol'&&c!=='seek')bothC=Date.now();if(c==='stop')bothStop();else if(c==='pause')AU.pause();else if(c==='resume'&&lp)AU.play().catch(()=>{});else if(c==='vol')AU.volume=Math.max(0,Math.min(1,extra.v));else if(c==='seek'&&isFinite(AU.duration))AU.currentTime=extra.pos}
 await fetch('/api/preview/ctl',{method:'POST',body:JSON.stringify({cmd:c,...extra})});pvPoll()}
async function setPvTarget(v){
 PVCUR={id:null,state:'stopped'};const old=pvt();if(bsolo)soloLocal(false);
 if(old!=='pi'){AU.pause();lp=null;AU.removeAttribute('src');AU.load()}
 if(old!=='browser'&&PVDEV)await fetch('/api/preview/ctl',{method:'POST',body:JSON.stringify({cmd:'stop'})});
 try{localStorage.setItem('cp_pvtarget',v)}catch(e){}
 lastLib='';lastHtml='';render(true);pvPoll();if(v==='browser')renderLocal();else pvlbl.textContent='';fillPvTarget()}
function fillPvTarget(){
 const o='<option value=browser data-g="Plays on">This browser</option>'+(PVDEV?'<option value=pi data-g="Plays on">Player output ('+esc(PVDEV)+')</option><option value=both data-g="Plays on">Both: browser + player output</option>':'');
 for(const e of [set_pvt,pvsel,tr_pvt]){if(e.innerHTML!==o)e.innerHTML=o;e.value=pvt();cbSync(e)}
 set_pvnote.textContent={browser:"Plays through this device's speakers or headphones.",pi:"Plays on the player's own preview output.",both:'Plays on the player output and in this browser together.'}[pvt()]||'';setSums()}
pvseek.addEventListener('pointerdown',()=>pvSeeking=true);
pvseek.addEventListener('change',()=>{pvCtl('seek',{pos:+pvseek.value});pvSeeking=false});
pvvol.addEventListener('input',()=>{pvCtl('vol',{v:+pvvol.value});for(const a of MONA.values())a.volume=Math.max(0,Math.min(1,(a._dv||0)*(+pvvol.value)))});
async function savePreviewDev(){
 const r=await fetch('/api/preview/device',{method:'POST',body:JSON.stringify({name:set_pv.value||null})});
 let e={};if(!r.ok)e=await r.json().catch(()=>({}));
 say(r.ok?(set_pv.value?'Preview output set.':'Preview turned off.'):(e.error||'Could not use that device'),r.ok);if(!r.ok)await loadDevs();await render();fillPvTarget()}
function setHidOut(on){SHOWHID=!!on;try{localStorage.setItem('cp_show_hidden_out',on?'1':'0')}catch(e){}loadDevs()}
const cmd=async u=>{await fetch('/api/'+u);render()};
async function stopAll(){await fetch('/api/stopall');if(trdlg.open)trdlg.close();try{await pvCtl('stop')}catch(e){}lastHtml='';render(true)}
let vSent=-1,vTimer=null,volTouch=0;
function sendVol(){vTimer=null;const v=+livevol.value;if(v!==vSent){vSent=v;fetch('/api/volume/'+v);vTimer=setTimeout(sendVol,60)}}
livevol.addEventListener('input',()=>{volTouch=Date.now();livevolv.textContent=livevol.value+'%';if(!vTimer)sendVol()});
async function rescan(){scanHidden='';await fetch('/api/rescan');render(true)}
const THM={system:'System',light:'Light',dark:'Dark'};
function syncLook(){
 setTimeout(fitInf,0);
 thm.textContent=THM[LOOK.theme]+(LOOK.theme==='system'?' ('+document.documentElement.dataset.theme+')':'');
 set_skin.value=LOOK.skin;set_wave.checked=WAVE;wnFill();if(wn_body.hidden===wnOpen())wnTog();topLoad();trLoad();set_theme.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.v===LOOK.theme));setSums()}
/* Time warnings live on the player (state.json), so every page, and the stage page, use the same list. They are always on.
   WN.warnings is [{t: seconds left, c: colour}], longest first: the first row is "First warning", the last "Final warning". */
let WN={warnings:[{t:60,c:'#f97316'},{t:30,c:'#ef4444'}]},wnTouch=0,wnMig=false;
const ptime=s=>{const m=String(s).trim().match(/^(\d+):([0-5]?\d)$/);if(m)return +m[1]*60+ +m[2];return /^\d+$/.test(String(s).trim())?+s:null};
const wnLabel=(i,n)=>i===n-1?'Final warning':i===0?'First warning':'Warning '+(i+1);
const wnOpen=()=>{try{return localStorage.getItem('cp_wn_open')==='1'}catch(e){return false}};
function wnTog(){const o=wn_body.hidden;wn_body.hidden=!o;wn_toggle.setAttribute('aria-expanded',o);wn_ar.textContent=o?'▾':'▸';try{localStorage.setItem('cp_wn_open',o?'1':'0')}catch(e){}}
function wnSummary(){wn_sum.innerHTML=WN.warnings.map(w=>`<span class=dotc><i style="background:${esc(w.c)}"></i>${mmss(w.t)}</span>`).join('')}
function wnRows(){const n=WN.warnings.length;
 wn_rows.innerHTML=WN.warnings.map((w,i)=>`<div class="wn wr"><span class=wnn>${wnLabel(i,n)}</span><input data-i=${i} data-k=t value="${mmss(w.t)}" maxlength=7 size=7 onchange="wnEdit(this)" aria-label="${wnLabel(i,n)}, minutes:seconds remaining"><em>left</em><input type=color data-i=${i} data-k=c value="${esc(w.c)}" onchange="wnEdit(this)" aria-label="${wnLabel(i,n)} colour">${n>1?`<button class="ib wnx" onclick="wnDel(${i})" title="Remove this warning" aria-label="Remove ${wnLabel(i,n)}">✕</button>`:'<span class=wnx0></span>'}</div>`).join('');
 wnSummary()}
function wnFill(){const rows=wn_rows.querySelectorAll('.wn');if(rows.length!==WN.warnings.length){wnRows();return}
 const a=document.activeElement;wn_rows.querySelectorAll('input').forEach(e=>{if(e===a)return;const w=WN.warnings[+e.dataset.i];e.value=e.dataset.k==='t'?mmss(w.t):w.c});wnSummary()}   // a field being typed in is left alone
function wnEdit(el){const i=+el.dataset.i,w=WN.warnings[i];if(!w)return;
 const was=el.dataset.k==='t'?w.t:w.c;
 if(el.dataset.k==='t'){const t=ptime(el.value);if(t!==null&&t<=359999)w.t=t;el.value=mmss(w.t)}else w.c=el.value;
 if((el.dataset.k==='t'?w.t:w.c)===was)return;                          // nothing really changed (a field losing focus): do not send an older list over another browser's edit
 wnCommit()}
function wnAdd(){const mx=Math.max(...WN.warnings.map(w=>w.t));WN.warnings.push({t:Math.min(359999,mx+60),c:'#facc15'});wnCommit(true)}   // longer than the rest, so it becomes the First warning
function wnDel(i){if(WN.warnings.length<2)return;WN.warnings.splice(i,1);wnCommit(true)}
function wnCommit(rebuild){const old=WN.warnings,sorted=old.map((w,i)=>({w,i})).sort((a,b)=>b.w.t-a.w.t||a.i-b.i);   // longest first; the labels follow the order
 const moved=sorted.some((x,k)=>x.i!==k);WN.warnings=sorted.map(x=>x.w);
 if(moved||rebuild)wnRows();else wnSummary();
 wnApply(lastRem);wnPost()}
async function wnPost(){wnTouch=Date.now();try{const r=await fetch('/api/settings/warning',{method:'POST',body:JSON.stringify({warnings:WN.warnings})});if(!r.ok)return false;wnTouch=Date.now();return true}catch(e){return false}}
/* called with the "warning" part of every /api/state: adopt changes made in another browser; once, upload this browser's old copy if the player has none */
function wnSync(w){if(!w||!w.warnings)return;
 if(!w.set){if(wnMig)return;wnMig=true;let o=null;try{o=JSON.parse(localStorage.getItem('cp_warn')||'null')}catch(e){}
  if(o&&typeof o==='object'){const l=Array.isArray(o.warnings)?o.warnings:[{t:o.t1,c:o.c1},{t:o.t2,c:o.c2}];
   if(l.length&&l.every(x=>x&&Number.isFinite(+x.t)&&+x.t>=0&&/^#[0-9a-f]{6}$/i.test(x.c||''))){
    WN.warnings=l.map(x=>({t:Math.round(+x.t),c:x.c.toLowerCase()})).sort((a,b)=>b.t-a.t);wnFill();wnApply(lastRem);
    wnPost().then(ok=>{if(ok)try{localStorage.removeItem('cp_warn')}catch(e){}})}}
  return}
 if(Date.now()-wnTouch<2500)return;                                   // our own change is on its way: do not let an older answer undo it
 if(JSON.stringify(w.warnings)===JSON.stringify(WN.warnings))return;
 WN.warnings=w.warnings.map(x=>({t:x.t,c:x.c}));wnFill();wnApply(lastRem)}
let lastRem='--:--';
function wnApply(r){lastRem=r;let col='';
 if(/^\d+:\d\d$/.test(r)){const s=ptime(r);let best=null;for(const w of WN.warnings)if(s<=w.t&&(!best||w.t<=best.t))best=w;if(best)col=best.c}   // the colour of the shortest warning time still reached
 remv.style.color=col;if(window.ms_rem)ms_rem.style.color=col}
function setWave(v){WAVE=!!v;try{localStorage.setItem('cp_wave',WAVE?'1':'0')}catch(e){}document.body.classList.toggle('wave',WAVE);syncLook()}
function cycleTheme(){setLook('theme',{system:'light',light:'dark',dark:'system'}[LOOK.theme])}
try{matchMedia('(prefers-color-scheme: dark)').addEventListener('change',syncLook)}catch(e){}
function say(t,ok){setmsg.textContent=t;setmsg.className='msg '+(ok?'ok':'bad')}
let DFI='';
function dfiShow(){const n=DFI?DFI.replace(/-/g,' '):'Circle (default)';dfi_curi.innerHTML=DFI?icoSvg(DFI,18):'<span class=cdot></span>';dfi_curn.textContent=n[0].toUpperCase()+n.slice(1);
 dfi_grid.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.i===DFI))}
function dfiTog(open){const o=typeof open==='boolean'?open:dfi_grid.hidden;dfi_grid.hidden=!o;dfi_cur.setAttribute('aria-expanded',o);dfi_ar.textContent=o?'▴':'▾';dfi_cur.title=o?'Hide the icons':'Show all icons'}
async function dfiLoad(){try{DFI=(await j('/api/settings/folders')).default_icon||''}catch(e){}
 dfi_grid.innerHTML=`<button class="ic0${DFI?'':' on'}" data-i="" title="Circle (default)"><span class=cdot></span></button>`+Object.keys(ICONS).map(n=>`<button class="${n===DFI?'on':''}" data-i="${n}" title="${n.replace(/-/g,' ')}">${icoSvg(n,18)}</button>`).join('');dfiShow();dfiTog(false)}
dfi_grid.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;
 const r=await fetch('/api/settings/folders',{method:'POST',body:JSON.stringify({default_icon:b.dataset.i||''})});
 if(r.ok){DFI=b.dataset.i||'';dfiShow();dfiTog(false);say(b.dataset.i?'New folders will get the '+b.dataset.i.replace(/-/g,' ')+' icon.':'New folders get the plain circle.',true)}else say('Could not save.',false)});
async function openSettings(){setMode();dfiLoad();
 const s=await j('/api/settings');CMP={host:s.companion_host,port:s.companion_osc_port,target:s.target||s.companion_host+':'+s.companion_osc_port,prefix:s.variable_prefix??s.var_prefix??'',warn:null};
 CMP.found=s.host_found;set_host.value=s.companion_host;set_port.value=s.companion_osc_port;set_prefix.value=CMP.prefix;pfxWarn(null);pfx_resrow.hidden=true;pfxPreview();cmpWarn(null);cmp_res.hidden=true;pfxShow();
 await loadDevs();fillPvTarget();
 setTab(SETTAB);if(settings.classList.contains('sm'))setSec(null);set_search.value='';setFind('');layMenu(false);
 ffLoad();hsLoad();say('',true);setSums();settings.showModal()}
/* Settings layout: four tabs on a wide screen; on a phone or touch panel one column of sections, closed, one open at a time, with a search box. */
const SMQ=matchMedia('(max-width:34rem),(hover:none) and (pointer:coarse)');
function setMode(){settings.classList.toggle('sm',SMQ.matches)}
try{SMQ.addEventListener('change',setMode)}catch(e){}
let SETTAB='look';try{const t=localStorage.getItem('cp_set_tab');if(['look','audio','companion','system'].includes(t))SETTAB=t}catch(e){}
function setTab(t){SETTAB=t;settings.dataset.tab=t;try{localStorage.setItem('cp_set_tab',t)}catch(e){}
 set_tabs.querySelectorAll('button').forEach(b=>{const on=b.dataset.tab===t;b.classList.toggle('on',on);b.setAttribute('aria-selected',on)})}
function setSec(id){settings.querySelectorAll('.ss').forEach(x=>{const o=id!==null&&x.dataset.sec===id&&!x.classList.contains('open');x.classList.toggle('open',o);x.querySelector('.sh').setAttribute('aria-expanded',o)})}
function setFind(q){q=q.trim().toLowerCase();settings.classList.toggle('srch',!!q);
 const secs=settings.querySelectorAll('.ss');
 secs.forEach(x=>{let n=0;x.querySelectorAll('.sr').forEach(r=>{const hit=!q||(r.dataset.s+' '+r.textContent).toLowerCase().includes(q);r.classList.toggle('nm',!hit);if(hit)n++});
  x.classList.toggle('nm',!!q&&!n);if(q){x.classList.toggle('open',n>0);x.querySelector('.sh').setAttribute('aria-expanded',n>0)}});
 if(!q&&settings.classList.contains('sm'))setSec(null)}
/* the one-line summary of each section (shown when the section is closed on a phone) */
function setSums(){try{setSums1()}catch(e){}}
function setSums1(){
 const set=(id,t)=>{const e=document.getElementById('sum_'+id);if(e)e.textContent=t};
 const SK={console:'Console',studio:'Studio',stage:'Stage'};
 set('appearance',(SK[LOOK.skin]||LOOK.skin)+' · '+THM[LOOK.theme]+' theme');
 set('audio',({browser:'This browser',pi:'Player output',both:'Both'}[pvt()]||'')+' · Mirror '+(set_mir.checked?'on':'off')+(INP&&INP.device?' · Input '+(INP.armed?'armed':'off'):''));
 set('transitions',(TRD==='cut'?'Cut':'Crossfade')+' · crossfade '+(+tr_ms.value||0)+' s');
 set('companion',(CMP.warn?'Still using ':'')+cmpFmt(CMP.target));
 set('engine',(FFSUM||'FFmpeg …')+(appver.textContent?' · v'+appver.textContent.replace(/^Cue Media Engine /,''):''));
 set('library',FMTSUM||'…');set('health',HS?'Watchdog '+(HS.watchdog?'on':'off')+' · Push '+(HS.push&&HS.push.enabled?'on':'off'):'…')}
var FMTSUM='',FFSUM='';
/* tips: the (i) buttons open one sentence under their row */
settings.addEventListener('click',e=>{const b=e.target.closest('.ib2');if(!b)return;const row=b.closest('.sr'),n=row.nextElementSibling;
 if(n&&n.classList.contains('tipbox')&&n._b===b){n.remove();b.setAttribute('aria-expanded','false');return}
 const t=document.createElement('div');t.className='tipbox';t.setAttribute('role','note');t.textContent=b.dataset.tip;t._b=b;row.after(t);b.setAttribute('aria-expanded','true')});
function layMenu(o){const v=typeof o==='boolean'?o:lay_menu.hidden;lay_menu.hidden=!v;lay_more.setAttribute('aria-expanded',v)}
settings.addEventListener('pointerdown',e=>{if(!lay_menu.hidden&&!e.target.closest('#lay_menu,#lay_more'))layMenu(false)});
settings.addEventListener('keydown',e=>{if(e.key==='Escape'&&!lay_menu.hidden){e.preventDefault();e.stopPropagation();layMenu(false)}});
settings.addEventListener('close',()=>layMenu(false));
/* Companion address: saved when you leave the field; an incomplete one is refused and the last good address stays in use */
var CMP={host:'',port:'',target:'',prefix:'',warn:null},CMPSAVE=null,CMPBUSY=false;
const cmpFmt=t=>String(t||'').replace(/:(\d+)$/,' : $1');
function hostErr(h){
 if(!h)return 'Enter an IP address or a host name, e.g. 192.168.1.50.';
 if(h.includes(':'))return /^[0-9a-fA-F:.]+$/.test(h)&&h.split(':').length>=3?'':'That is not a complete IPv6 address.';
 if(!/^[A-Za-z0-9._-]+$/.test(h))return 'Use only letters, numbers, dots and dashes.';
 if(/^[0-9.]+$/.test(h)){const p=h.split('.');return p.length===4&&p.every(x=>/^\d{1,3}$/.test(x)&&+x<=255)?'':'An IP address has four numbers from 0 to 255, e.g. 192.168.1.50.'}
 return /^[.-]|[.-]$|\.\./.test(h)?'Check the host name.':''}
function cmpWarn(title,msg,field){CMP.warn=title?{title,msg,field}:null;
 cmp_warn.hidden=!title;cmp_warn.innerHTML=title?`<b>${esc(title)}</b> ${esc(msg)} The player is still sending to ${esc(cmpFmt(CMP.target))}.`:'';
 set_host.classList.toggle('bad',!!title&&field==='host');set_port.classList.toggle('bad',!!title&&field==='port');cmpShow()}
function cmpShow(){cmp_to.textContent=cmpFmt(CMP.target);cmp_note.hidden=CMP.found!==false||!!CMP.warn;setSums()}
async function cmpSave(){
 const host=set_host.value.trim(),port=set_port.value.trim();
 const he=hostErr(host);if(he){cmpWarn('Incomplete address.',he,'host');return}
 if(!/^\d+$/.test(port)||+port<1||+port>65535){cmpWarn('Port not valid.','Use a number from 1 to 65535.','port');return}
 if(host===CMP.host&&+port===+CMP.port){cmpWarn(null);return}
 return CMPSAVE=(async()=>{try{const r=await fetch('/api/settings',{method:'POST',body:JSON.stringify({companion_host:host,companion_osc_port:port})});const d=await r.json().catch(()=>({}));
  if(r.ok){CMP.host=host;CMP.port=+port;CMP.target=d.target;CMP.found=d.host_found;cmpWarn(null);say('Companion address saved. Sending to '+cmpFmt(d.target)+'.',true)}
  else cmpWarn("Can't use that address.",d.error||'The player could not use it.','host')}
  catch(e){cmpWarn('Could not save.','The player did not answer.','host')}})()}
/* Variable prefix: checked when you leave the field; a bad one is refused (the last good one stays in use); a changed one asks first, because Companion buttons that
   use the old names stop working */
const PFXRE=/^[A-Za-z][A-Za-z0-9_]{0,15}$/;
/* every poll: a prefix changed in another browser (or by the config) shows here without a reload; a field being typed in is left alone */
function pfxSync(p){if(typeof p!=='string'||p===CMP.prefix||pfxdlg.open)return;CMP.prefix=p;if(document.activeElement!==set_prefix){set_prefix.value=p;pfxPreview()}pfxShow()}
function pfxShow(){cmp_vars.textContent=CMP.prefix+'live_name, '+CMP.prefix+'remaining …';setSums()}
function pfxPreview(){const v=set_prefix.value;pfx_ex.textContent=PFXRE.test(v)?'Example: '+v+'remaining':''}
function pfxWarn(msg){pfx_warn.hidden=!msg;pfx_warn.innerHTML=msg?`<b>Invalid prefix.</b> ${esc(msg)} The player is still using ${esc(CMP.prefix)}.`:'';set_prefix.classList.toggle('bad',!!msg)}
function pfxAsk(o,n){return new Promise(res=>{pfxdlg._r=res;pfx_old.textContent=o;pfx_new.textContent=n;pfxdlg.returnValue='';pfxdlg.showModal()})}
pfxdlg.addEventListener('close',()=>{const r=pfxdlg._r;pfxdlg._r=null;if(r)r(pfxdlg.returnValue==='ok')});
/* the result chip: green only when the variables really went out under the new names; when Companion could not be reached the prefix is saved but the chip says so */
function pfxResult(d){pfx_resrow.hidden=false;const ok=d.sending!==false;
 pfx_res.className='chipb '+(ok?'ok':'bad');pfx_res.textContent=ok?d.prefix+'… sent':d.prefix+'… saved, Companion not reached';
 say(ok?'Variable prefix changed. Every variable was sent again as '+d.prefix+'…':'Variable prefix saved as '+d.prefix+'…, but Companion could not be reached. The variables go out under the new names as soon as it can be.',ok)}
async function pfxSave(){
 const v=set_prefix.value.trim();pfx_resrow.hidden=true;
 if(!PFXRE.test(v)){pfxWarn(v?'Use 1 to 16 letters, digits or underscores, starting with a letter.':'Enter a prefix: 1 to 16 letters, digits or underscores, starting with a letter.');return}
 pfxWarn(null);if(v===CMP.prefix){pfxPreview();return}
 if(!await pfxAsk(CMP.prefix,v)){set_prefix.value=CMP.prefix;pfxPreview();return}
 try{const r=await fetch('/api/settings/prefix',{method:'POST',body:JSON.stringify({prefix:v,confirm:true})});const d=await r.json().catch(()=>({}));
  if(r.ok&&d.ok){CMP.prefix=d.prefix;set_prefix.value=d.prefix;pfxPreview();pfxShow();pfxResult(d)}
  else{pfxWarn(d.error||'The player could not use it.');set_prefix.value=CMP.prefix;pfxPreview()}}
 catch(e){pfxWarn('The player did not answer.')}}
async function cmpTest(){
 if(CMPBUSY)return;CMPBUSY=true;cmp_test.disabled=true;let d;
 try{if(CMPSAVE)await CMPSAVE;const r=await fetch('/api/settings/companion/test',{method:'POST'});d=await r.json()}catch(e){d={ok:false,error:'The player did not answer'}}
 const to=cmpFmt(d.sent_to||CMP.target);if('host_found' in d){CMP.found=d.host_found;cmpShow()}
 cmp_res.className='resbox '+(d.ok?'ok':'bad');
 cmp_res.innerHTML=d.ok?`<b>Test sent</b>${esc(to)} at ${esc(d.at)}. Look for <b class=inl>${esc(CMP.prefix)}test</b> in Companion's variables.`:`<b>Couldn't send</b>${esc(d.error||'Unknown error')}. Still using ${esc(to)}.`;
 cmp_res.hidden=false;CMPBUSY=false;cmp_test.disabled=false}
let fmtTimer=null;
async function fmtLoad(){try{const f=await j('/api/formats');
 const chip=(t,k)=>{fmt_chip.textContent=t;fmt_chip.className='chipb'+(k?' '+k:'');FMTSUM=t;setSums()};
 if(!f.available){chip('Needs ffmpeg','');fmt_status.textContent='Needs ffmpeg. Without it, files that cannot be read are marked with a red sign once their length is measured.';return}
 const p=f.problems||[];
 if(f.running)chip(`Checking… ${f.done} of ${f.total}`,'');else if(p.length)chip(p.length+(p.length===1?' file needs attention':' files need attention'),'bad');else chip('All files look fine','ok');
 fmt_status.innerHTML=p.length?p.slice(0,30).map(x=>`${x.lv==='error'?'⛔':'⚠'} ${esc(x.id)}: ${esc(x.msg)}`).join('<br>')+(p.length>30?`<br>…and ${p.length-30} more`:''):'';
 clearTimeout(fmtTimer);if(f.running&&settings.open)fmtTimer=setTimeout(fmtLoad,1500);else if(!f.running){setLib(await j('/api/library'));lastLib='';renderLib()}}catch(e){fmt_chip.textContent='Could not check';fmt_chip.className='chipb bad'}}
async function fmtDeep(){fmt_chip.textContent='Starting…';fmt_chip.className='chipb';try{await j('/api/formats?deep=1')}catch(e){}fmtLoad()}
async function ffLoad(){fmtLoad();try{const f=await j('/api/ffmpeg');
 const v=((f.version||'').match(/^\d+(\.\d+)*/)||[''])[0];
 ff_chip.textContent=f.ok?(v?v+' found':'Found'):'Not found';ff_chip.className='chipb '+(f.ok?'ok':'bad');FFSUM=f.ok?'FFmpeg found':'FFmpeg missing';
 ff_tip.dataset.tip=f.ok?'Used to import other formats and convert uploads to 48 kHz.':`Not found: ${f.error}. The player works without it, but only wav, mp3, ogg and flac files can be imported and the built-in tools are used for waveforms and level matching.`}
 catch(e){ff_chip.textContent='Could not check';ff_chip.className='chipb bad';FFSUM='FFmpeg ?'}setSums()}
async function resendVars(){await fetch('/api/resend');say('Variables sent to Companion again.',true)}
let TRD='cut';
async function trLoad(){try{const r=await j('/api/settings/transition');TRD=r.default;tr_ms.value=(r.crossfade_ms/1000).toString();tr_fd.value=(r.trim_fade_ms/1000).toString();TRFADE=r.trim_fade_ms;tr_fi.value=((r.trim_fadein_ms||0)/1000).toString();TRFADEIN=r.trim_fadein_ms||0;document.querySelectorAll('#tr_seg button').forEach(b=>b.classList.toggle('on',b.dataset.v===TRD));setSums()}catch(e){}}
async function tranSave(v){if(v)TRD=v;const r=await fetch('/api/settings/transition',{method:'POST',body:JSON.stringify({default:TRD,crossfade_s:+tr_ms.value,trim_fade_s:+tr_fd.value,trim_fadein_s:+tr_fi.value})});
 const d=await r.json().catch(()=>({}));say(r.ok?'Transition settings saved.':(d.error||'Could not save.'),r.ok);trLoad()}
async function topLoad(){try{const r=await j('/api/settings/top');dk_thr.value=r.threshold_db;dk_rat.value=r.ratio;dk_att.value=r.attack_ms;dk_rel.value=r.release_ms;top_trk.value=r.track_pct;dk_hold.checked=!!r.hold;dkInfo()}catch(e){}}
const GRMAX=30;try{dk_grm.style.setProperty('--grmax',GRMAX)}catch(e){}
function duckTog(open){hintClose();const c=open===undefined?!potrow.classList.contains('dkc'):!open;potrow.classList.toggle('dkc',c);duckar.textContent=c?'▸':'▾';duckt.setAttribute('aria-expanded',String(!c));try{localStorage.setItem('cp_duck',c?'0':'1')}catch(e){}}
try{if(localStorage.getItem('cp_duck')==='1')duckTog(true)}catch(e){}
let dkTouch=0;potrow.addEventListener('pointerdown',()=>{dkTouch=Date.now()});
function dkInfo(){duck_sum.textContent=(+dk_thr.value).toFixed(0)+' dB · '+dk_rat.value+':1 · '+dk_att.value+'/'+dk_rel.value+' ms';dk_thr_v.textContent=(+dk_thr.value).toFixed(1)+' dB';dk_rat_v.textContent=(+dk_rat.value)+':1';dk_att_v.textContent=dk_att.value+' ms';dk_rel_v.textContent=dk_rel.value+' ms';top_trk_v.textContent=top_trk.value+'%';
 potrow.title='Play on Top: while the top track is louder than '+(+dk_thr.value).toFixed(1)+' dB the background is turned down by (dB over) x (1 - 1/'+dk_rat.value+'). It goes down in '+dk_att.value+' ms and comes back in '+dk_rel.value+' ms.'}
async function dkSave(){const r=await fetch('/api/settings/top',{method:'POST',body:JSON.stringify({threshold_db:+dk_thr.value,ratio:+dk_rat.value,attack_ms:+dk_att.value,release_ms:+dk_rel.value,track_pct:+top_trk.value,hold:dk_hold.checked})});
 const d=await r.json().catch(()=>({}));say(r.ok?'Ducking saved.':(d.error||'Could not save.'),r.ok);if(!r.ok)topLoad()}
setTimeout(topLoad,0);
async function restartPlayer(){
 if(!confirm('Restart the player now?\n\nAudio stops for a few seconds. A track that is playing carries on from where it was.'))return;
 try{await fetch('/api/restart',{method:'POST'})}catch(e){}
 healthSync({status:'starting',state:'starting',summary:'Restarting',detail:'Restarting...',checks:[]});say('Restarting the player...',true);
 const t0=Date.now();await new Promise(r=>setTimeout(r,1500));
 while(Date.now()-t0<60000){try{const r=await fetch('/api/state',{cache:'no-store'});if(r.ok){location.reload();return}}catch(e){}await new Promise(r=>setTimeout(r,700))}
 say('The player did not come back within a minute. Check the service on the machine.',false)}
async function rescanLib(){await rescan();say('Library rescanned.',true)}
async function addpl(){await fetch('/api/playlists',{method:'POST',body:JSON.stringify({name:newpl.value||'Playlist'})});newpl.value='';await render(true);plChip('Created playlist')}
let COLL=new Set();try{COLL=new Set(JSON.parse(localStorage.getItem('cp_coll')||'[]'))}catch(e){}
const isColl=p=>COLL.has(p.name);
function togglePl(i){const n=PL[i].name;COLL.has(n)?COLL.delete(n):COLL.add(n);try{localStorage.setItem('cp_coll',JSON.stringify([...COLL]))}catch(e){}lastHtml='';renderLists(LASTS)}
async function renamePl(i){
 const card=lists.querySelector(`.pl[data-i="${i}"]`),b=card&&card.querySelector('.pln');if(!b)return;
 b.innerHTML='<input class=pn maxlength=80>';const inp=b.querySelector('input');inp.value=PL[i].name;inp.focus();inp.select();
 let done=false;
 const fin=async ok=>{if(done)return;done=true;const v=inp.value.trim();
  if(ok&&v&&v!==PL[i].name)await fetch(`/api/playlists/${i}/rename`,{method:'POST',body:JSON.stringify({name:v})});
  inp.onblur=null;inp.blur();lastHtml='';render(true)};
 inp.onkeydown=e=>{if(e.key==='Enter')fin(true);else if(e.key==='Escape')fin(false)};inp.onblur=()=>fin(true)}
async function movePl(i,j){
 if(j<0||j>=PL.length||i===j)return;
 const r=await fetch('/api/playlists/reorder',{method:'POST',body:JSON.stringify({from:i,to:j})});
 if(!r.ok)alert('Could not move the playlist');render(true)}
async function delpl(i){
 if(!confirm('Delete the playlist "'+PL[i].name+'"?\nIts tracks stay in the library.'))return;
 await fetch('/api/playlists/'+i,{method:'DELETE'});render(true)}
async function rm(i,k){await fetch(`/api/playlists/${i}/${k}`,{method:'DELETE'});render(true)}
async function mv(fp,ft,tp,ti){
 const r=await fetch('/api/move',{method:'POST',body:JSON.stringify({from:[fp,ft],to:[tp,ti]})});
 if(!r.ok){const e=await r.json().catch(()=>({}));alert('Could not move the track ('+(e.result||r.status)+')')}
 render(true)}
async function addToPl(p,ids,index){
 const r=await fetch(`/api/playlists/${p}/add`,{method:'POST',body:JSON.stringify({files:ids,index:index})});
 if(!r.ok)alert('Could not add to the playlist');render(true)}
async function delLib(id){
 const f=LIBF.find(x=>x.id===id);if(!f)return;
 const where=f.used.length?`\n\nIt is used in ${f.used.length} playlist(s) (${f.used.map(n=>PL[n]?PL[n].name:n).join(', ')}) and will be removed from them.`:'';
 if(!confirm(`Delete "${f.name}" from the library?${where}\n\nThe audio file will be permanently deleted.`))return;
 const r=await fetch('/api/library?id='+encodeURIComponent(id),{method:'DELETE'});
 if(!r.ok)alert('Could not delete the file');render(true)}
lists.addEventListener('click',e=>{                    // click a track row (not a button, menu or handle) to focus it
 const li=e.target.closest('li.t');if(!li)return;
 if(e.target.closest('.flag')){flashFolder(li.dataset.fid);return}
 if(e.target.closest('button,select,input,a,.grip,.pvslot'))return;
 cmd(li.dataset.i+'/'+li.dataset.k+'/focus')});
const libCmp=(a,b)=>{const x=a.split('/'),y=b.split('/'),n=Math.min(x.length,y.length);   // same order as the tree: sub-folders first, then files, A-Z
 for(let i=0;i<n;i++){if(x[i]===y[i])continue;const fx=i===x.length-1,fy=i===y.length-1;if(fx!==fy)return fx?1:-1;return x[i].toLowerCase().localeCompare(y[i].toLowerCase(),undefined,{numeric:true})}return x.length-y.length};
const libOrder=()=>[...lib.querySelectorAll('.lt[data-id]')].map(x=>x.dataset.id);
function selUi(){const n=SEL.size;selbar.hidden=!n;if(!n){selbar.innerHTML='';return}
 selbar.innerHTML=`<b>${n} selected</b><span class=dim>drag them to a playlist</span>${PL.length?`<select id=selpl><option value="">Add to…</option>${PL.map((p,i)=>`<option value=${i}>${esc(p.name)}</option>`).join('')}</select>`:''}<button id=selclr>Clear</button>`}
function selClear(){SEL.clear();selAnchor=null;lastLib='';renderLib();selUi()}
selbar.addEventListener('click',e=>{if(e.target.id==='selclr')selClear()});
selbar.addEventListener('change',e=>{if(e.target.id==='selpl'&&e.target.value!==''){const ids=libOrder().filter(x=>SEL.has(x)),p=+e.target.value;selClear();addToPl(p,ids,1e9)}});
function selClick(e){const row=e.target.closest('.lt[data-id]');if(!row||e.target.closest('button,select,.ib'))return false;
 const id=row.dataset.id;
 if(e.shiftKey&&selAnchor){const o=libOrder(),a=o.indexOf(selAnchor),b=o.indexOf(id);if(a>=0&&b>=0){if(!(e.ctrlKey||e.metaKey))SEL.clear();for(const x of o.slice(Math.min(a,b),Math.max(a,b)+1))SEL.add(x)}}
 else if(e.ctrlKey||e.metaKey||SEL.size){SEL.has(id)?SEL.delete(id):SEL.add(id);selAnchor=id}
 else return false;
 lastLib='';renderLib();selUi();return true}
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&SEL.size)selClear()});
lib.addEventListener('click',e=>{
 if(selClick(e)){e.preventDefault();return}
 const fd=e.target.closest('.fd'),act=e.target.closest('[data-act]');
 if(fd&&act&&!act.disabled){const path=fd.dataset.path,a=act.dataset.act;
  if(a==='tog'){closed.has(path)?closed.delete(path):closed.add(path);saveClosed();lastLib='';renderLib()}
  else if(a==='fav')flagSet(path,{fav:!flOf(path).fav});else if(a==='hide')flagSet(path,{hidden:true});else if(a==='unhide')flagSet(path,{hidden:false});
  else if(a==='newf')openFd('newf',path,act);else if(a==='renf')openFd('renf',path,act);else if(a==='delf')delFolder(path);else if(a==='color')openColor(path,act);return}
 const hm=e.target.closest('.hidmsg');if(hm){SREV=hm.dataset.act==='revhid';lastLib='';renderLib();return}
 const ip=e.target.closest('[data-act=inpl]');if(ip){cycleUsed(ip.closest('.lt').dataset.id);return}
 const rn=e.target.closest('[data-act=ren]');if(rn){openFd('ren',rn.closest('.lt').dataset.id,rn);return}
 const b=e.target.closest('[data-act=del]');if(b)delLib(b.closest('.lt').dataset.id);
 const v=e.target.closest('[data-act=pv]');if(v)pvPlay({id:v.closest('.lt').dataset.id})});
lib.addEventListener('keydown',e=>{const hm=e.target.closest&&e.target.closest('.hidmsg');if(hm&&(e.key==='Enter'||e.key===' ')){e.preventDefault();hm.click()}});
lib.addEventListener('change',e=>{const s=e.target.closest('select[data-act=add]');
 if(s&&s.value!==''){const id=s.closest('.lt').dataset.id,p=+s.value;s.value='';addToPl(p,[id],1e9)}});

let FD=null;
function openFd(mode,arg,anchor){
 FD={mode,arg};fdmsg.textContent='';
 const isFile=mode==='ren',base=arg.slice(arg.lastIndexOf('/')+1),parent=arg.includes('/')?arg.slice(0,arg.lastIndexOf('/')):'';
 const ban=mode==='renf'?(d=>d===arg||d.startsWith(arg+'/')):(()=>false);
 fd_folder.innerHTML='<option value="">(top level)</option>'+LIBD.filter(d=>!ban(d)).map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join('');
 if(mode==='newf'){fdtitle.textContent=arg?'New folder in "'+arg+'"':'New folder';fd_name.value='';fd_ext.textContent='';fd_frow.style.display='none'}
 else if(mode==='renf'){fdtitle.textContent='Rename or move folder';fd_name.value=base;fd_ext.textContent='';fd_frow.style.display='';fd_folder.value=parent}
 else{const ext=base.includes('.')?base.slice(base.lastIndexOf('.')):'';fdtitle.textContent='Rename or move track';
  fd_name.value=ext?base.slice(0,-ext.length):base;fd_ext.textContent=ext;fd_frow.style.display='';fd_folder.value=parent}
 const sy=scrollY,ar=anchor&&anchor.isConnected?anchor.getBoundingClientRect():null;   // showModal() jumps the page to the top: note where things were first
 fdlg.showModal();scrollTo(0,sy);fdPlace(ar);fd_name.focus({preventScroll:true});fd_name.select()}
/* open next to the button that was clicked (below it, or above if there is no room), kept on screen */
function fdPlace(r){fdlg.style.position=fdlg.style.margin=fdlg.style.left=fdlg.style.top='';if(!r)return;
 const w=fdlg.offsetWidth,h=fdlg.offsetHeight,M=8;
 fdlg.style.position='fixed';fdlg.style.margin='0';
 fdlg.style.left=Math.max(M,Math.min(r.left+r.width/2-w/2,innerWidth-w-M))+'px';
 const below=r.bottom+6;fdlg.style.top=Math.max(M,Math.min(innerHeight-h-M,below+h<=innerHeight-M?below:r.top-6-h))+'px'}
fdlg.addEventListener('close',()=>{fdlg.style.position=fdlg.style.margin=fdlg.style.left=fdlg.style.top=''});
fdlg.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing&&!e.target.closest('button')){e.preventDefault();fdSave()}});
let fdBusy=false;
async function fdSave(){
 if(fdBusy)return;fdBusy=true;try{await fdSave2()}finally{fdBusy=false}}
async function fdSave2(){
 const name=fd_name.value.trim();
 if(!name){fdmsg.textContent='Type a name.';return}
 if(/[\/\\]/.test(name)){fdmsg.textContent='A name cannot contain / or \\ (use the Parent Folder menu to move it).';return}
 let r;
 if(FD.mode==='newf')r=await fetch('/api/library/folder',{method:'POST',body:JSON.stringify({path:(FD.arg?FD.arg+'/':'')+name})});
 else{const dest=fd_folder.value,to=(dest?dest+'/':'')+name+(FD.mode==='ren'?fd_ext.textContent:'');
  r=await fetch('/api/library/rename',{method:'POST',body:JSON.stringify({from:FD.arg,to})})}
 const d=await r.json().catch(()=>({}));
 if(!r.ok){fdmsg.textContent=d.error||'That did not work.';return}
 if(FD.mode==='newf')closed.delete(FD.arg);
 fdlg.close();lastLib='';lastHtml='';render(true)}
async function delFolder(path){
 const pre=path+'/',fl=LIBF.filter(x=>x.id.startsWith(pre)),sub=LIBD.filter(d=>d.startsWith(pre)).length;
 let force='';
 if(!fl.length&&!sub){if(!confirm('Delete the empty folder "'+path+'"?'))return}
 else{
  const pls=[...new Set(fl.flatMap(f=>f.used))].sort((a,b)=>a-b).map(n=>PL[n]?PL[n].name:n);
  const msg=`Delete the folder "${path}" and everything in it?\n\n`+`${fl.length} audio file(s)`+(sub?` and ${sub} sub-folder(s)`:'')+` will be permanently deleted.`
   +(pls.length?`\n\nTracks from it are used in ${pls.length} playlist(s) (${pls.join(', ')}) and will be removed from them.`:'');
  if(!confirm(msg))return;force='&force=1'}
 const r=await fetch('/api/library/folder?path='+encodeURIComponent(path)+force,{method:'DELETE'});
 if(!r.ok){const d=await r.json().catch(()=>({}));alert(d.error||'Could not delete the folder')}
 lastLib='';render(true)}
async function moveToFolder(id,path){
 const to=(path?path+'/':'')+id.slice(id.lastIndexOf('/')+1);if(to===id)return;
 const r=await fetch('/api/library/rename',{method:'POST',body:JSON.stringify({from:id,to})});
 if(!r.ok){const d=await r.json().catch(()=>({}));alert(d.error||'Could not move the file')}
 lastLib='';lastHtml='';render(true)}
let PFL={i:-1,fid:null,until:0},CYC={};
function cycleUsed(fid){                  // the reverse of the quick flag: from a library file to the playlists that hold it, one per click
 const f=LIBF.find(x=>x.id===fid);if(!f||!f.used.length)return;
 const used=[...f.used].sort((a,b)=>a-b);
 let n=CYC[fid]===undefined?0:(CYC[fid]+1)%used.length;CYC[fid]=n;
 const i=used[n],p=PL[i];if(!p)return;
 COLL.delete(p.name);try{localStorage.setItem('cp_coll',JSON.stringify([...COLL]))}catch(e){}
 PFL={i,fid,until:Date.now()+4000};lastHtml='';renderLists(LASTS);
 const el=lists.querySelector(`li.t[data-i="${i}"][data-fid="${CSS.escape(fid)}"]`);
 if(el)el.scrollIntoView({block:'center',behavior:'smooth'});
 const b=lib.querySelector(`.lt[data-id="${CSS.escape(fid)}"] .inpl`);if(b)b.title=`Showing playlist ${n+1} of ${used.length}: ${p.name}. Click for the next one.`;
 setTimeout(()=>{lastHtml='';renderLists(LASTS)},4100)}
function flashFolder(fid){          // show where a track lives: open its folders in the library and flash the track itself yellow for 4 seconds
 const i=fid.lastIndexOf('/'),path=i<0?'':fid.slice(0,i);
 q.value='';
 if(path){let c='';for(const seg of path.split('/')){c=c?c+'/'+seg:seg;closed.delete(c)}saveClosed()}
 FLASH={path:null,id:fid,until:Date.now()+4000};
 lastLib='';renderLib();
 const el=lib.querySelector(`.lt[data-id="${CSS.escape(fid)}"]`);
 if(el)el.scrollIntoView({block:'center',behavior:'smooth'});
 setTimeout(()=>{lastLib='';renderLib()},4100)}
/* Folder icons: a selection of Lucide icons (https://lucide.dev, ISC licence), drawn inline so the page needs no internet */
//@include icons.js
function icoSvg(n,sz){return n&&ICONS[n]?`<svg width=${sz} height=${sz} viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round>${ICONS[n]}</svg>`:''}
const PAL=['#ef4444','#f97316','#22c55e','#14b8a6','#3b82f6','#6366f1','#a855f7','#ec4899','#94a3b8'];
function openColor(path,el){
 const cur=LIBI[path]||'';
 cpop.innerHTML='<div class=cph>Colour</div>'+PAL.map(c=>`<button class=sw data-c="${c}" style="--c:${c}" title="${c}"></button>`).join('')+'<button class="sw" data-c="" title="No colour">✕</button>'
  +`<div class=cph>Icon</div><div class=icg><button class="ic0${cur?'':' on'}" data-i="" title="Circle (default)"><span class=cdot></span></button>`
  +Object.keys(ICONS).map(n=>`<button class="${n===cur?'on':''}" data-i="${n}" title="${n.replace(/-/g,' ')}">${icoSvg(n,18)}</button>`).join('')+'</div>';
 cpop.dataset.path=path;cpop.hidden=false;const r=el.getBoundingClientRect();
 cpop.style.left=Math.max(4,Math.min(r.left,innerWidth-cpop.offsetWidth-8))+'px';cpop.style.top=Math.max(4,Math.min(r.bottom+4,innerHeight-cpop.offsetHeight-8))+'px'}
cpop.addEventListener('click',async e=>{const sw=e.target.closest('.sw'),ib=e.target.closest('.icg button');if(!sw&&!ib)return;const path=cpop.dataset.path;
 if(sw){await fetch('/api/library/folder/color',{method:'POST',body:JSON.stringify({path,color:sw.dataset.c||null})});cpop.hidden=true}
 else{await fetch('/api/library/folder/color',{method:'POST',body:JSON.stringify({path,icon:ib.dataset.i||null})});LIBI[path]=ib.dataset.i||'';cpop.querySelectorAll('.icg button').forEach(x=>x.classList.toggle('on',x===ib))}
 lastLib='';lastHtml='';render(true)});
document.addEventListener('click',e=>{if(!cpop.hidden&&!e.target.closest('#cpop,[data-act=color]'))cpop.hidden=true},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape')cpop.hidden=true});
/* Cbo: one searchable dropdown. cboOpen({anchor, items:[{v,t,sub,k,pin,dis}], current, onChoose, onClose, max, empty, placeholder, label})
   fills the shared popover #cbo. cbEnhance(select) puts a combobox button in front of a native <select> (kept in the page, hidden,
   as the source of truth: same id, same .value, same change event). The list is rebuilt only by cboOpen or cboSetItems. */
const cbNorm=s=>String(s).toLowerCase().replace(/[^\p{L}\p{N}]+/gu,'');
const CBO={on:false,anchor:null,items:[],vis:[],act:-1,cur:'',o:null};
const CBP=typeof cbo.showPopover==='function';
function cboMatch(it,q){if(!q.words.length)return true;const h=cbNorm(it.k||(it.t+' '+(it.sub||'')));return h.includes(q.all)||q.words.every(w=>h.includes(w))}
function cboRender(keepV){
 const o=CBO.o,qs=cbo_q.value,q={words:qs.split(/\s+/).map(cbNorm).filter(Boolean),all:cbNorm(qs)};
 const pins=CBO.items.filter(x=>x.pin),rest=CBO.items.filter(x=>!x.pin&&cboMatch(x,q)),shown=rest.slice(0,o.max||1000);
 CBO.vis=pins.concat(shown);
 let curDone=false;
 const row=(x,n)=>{const cur=!curDone&&x.v===CBO.cur&&!x.dis;if(cur)curDone=true;x.cur=cur;
  return `<div role=option id=cbo_o${n} data-n=${n} class="cbo-i${cur?' cur':''}${x.pin?' pin':''}${x.pin&&n===pins.length-1?' last':''}${x.hid?' hid':''}" aria-selected=${cur} title="${escAttr(x.title||x.t)}" ${x.dis?'aria-disabled=true':''}><span>${esc(x.t)}</span>${x.sub?`<small>${esc(x.sub)}</small>`:''}</div>`};
 let lastG='';
 cbo_l.innerHTML=CBO.vis.map((x,n)=>{let g='';if(!x.pin&&x.g&&x.g!==lastG){lastG=x.g;g=`<div class=cbo-g role=presentation>${esc(x.g)}</div>`}return g+row(x,n)}).join('')+(shown.length?'':`<div class=none role=presentation>${esc(o.empty||'No devices match')}</div>`);
 let a=keepV!=null?CBO.vis.findIndex(x=>x.v===keepV&&!x.dis):-1;
 if(a<0&&q.words.length)a=CBO.vis.findIndex(x=>!x.pin&&!x.dis);
 if(a<0)a=CBO.vis.findIndex(x=>x.cur);
 if(a<0)a=CBO.vis.findIndex(x=>!x.dis);
 cboActive(a,true)}
function cboActive(n,scroll){
 const old=cbo_l.querySelector('.cbo-i.on');old&&old.classList.remove('on');
 CBO.act=n;const e=n>=0?document.getElementById('cbo_o'+n):null;
 if(e){e.classList.add('on');cbo_q.setAttribute('aria-activedescendant',e.id);
  if(scroll){const t=e.offsetTop-cbo_l.offsetTop,h=e.offsetHeight;if(t<cbo_l.scrollTop)cbo_l.scrollTop=t;else if(t+h>cbo_l.scrollTop+cbo_l.clientHeight)cbo_l.scrollTop=t+h-cbo_l.clientHeight}}
 else cbo_q.removeAttribute('aria-activedescendant')}
function cboMove(d,abs){
 const v=CBO.vis,ok=i=>v[i]&&!v[i].dis;let n=CBO.act;
 if(abs!=null){n=abs<0?v.length-1:0;while(n>=0&&n<v.length&&!ok(n))n+=abs<0?-1:1}
 else{n+=d;while(n>=0&&n<v.length&&!ok(n))n+=d>0?1:-1;if(n<0||n>=v.length)return}
 if(ok(n))cboActive(n,true)}
function cboPlace(){      // fully inside the visible viewport (the layout viewport without the scrollbars), 8 px from every edge
 const M=8,r=CBO.anchor.getBoundingClientRect(),vw=document.documentElement.clientWidth,vh=document.documentElement.clientHeight;
 const w=Math.max(Math.min(vw-2*M,Math.min(Math.max(r.width,440),540)),Math.min(220,vw-2*M));
 cbo.style.width=w+'px';cbo.style.maxWidth=(vw-2*M)+'px';
 let left=r.left;if(left+w>vw-M)left=r.right-w;left=Math.max(M,Math.min(left,vw-M-w));      // near the right edge the menu's right edge lines up with the button's
 cbo.style.left=left+'px';cbo.style.right='auto';
 cbo_l.style.maxHeight='none';
 const chrome=cbo.offsetHeight-cbo_l.offsetHeight,nat=cbo_l.scrollHeight,gap=4,below=vh-r.bottom-M-gap,above=r.top-M-gap,cap=Math.max(120,Math.min(340,nat));
 const down=chrome+Math.min(nat,cap)<=below||below>=above,room=(down?below:above)-chrome;
 cbo_l.style.maxHeight=Math.max(48,Math.min(cap,room))+'px';       // the search box stays on top, the list scrolls inside its own box
 if(down){cbo.style.top=Math.max(M,Math.min(r.bottom+gap,vh-M-cbo.offsetHeight))+'px';cbo.style.bottom='auto'}
 else{cbo.style.top='auto';cbo.style.bottom=Math.max(M,vh-r.top+gap)+'px'}
 cbo.dataset.side=down?'down':'up';CBO.rect=r
 let b=cbo.getBoundingClientRect();         // last word: whatever the anchor does (half off screen, a tiny viewport), the box ends up inside the margins
 if(b.top<M){cbo_l.style.maxHeight=Math.max(0,cbo_l.clientHeight-(M-b.top))+'px';b=cbo.getBoundingClientRect()}
 if(b.bottom>vh-M){if(cbo.style.top==='auto'){cbo.style.bottom=Math.max(M,parseFloat(cbo.style.bottom)+(b.bottom-(vh-M)))+'px'}else{cbo.style.top=Math.max(M,vh-M-b.height)+'px'}}}
/* follow the button: a resize, a scroll, the Visual Viewport changing (pinch zoom, the on-screen keyboard) re-places the menu; when its button has scrolled out of view the menu closes */
function cboFollow(e){if(!CBO.on||(e&&e.target&&e.target!==window&&e.target!==document&&cbo.contains(e.target)))return;
 const r=CBO.anchor.getBoundingClientRect(),vw=document.documentElement.clientWidth,vh=document.documentElement.clientHeight;
 if(!CBO.anchor.isConnected||r.bottom<=0||r.top>=vh||r.right<=0||r.left>=vw||!r.width){cboClose(true);return}
 cboPlace()}
function cboOpen(o){
 if(CBO.on)cboClose(true);
 CBO.o=o;CBO.anchor=o.anchor;CBO.items=o.items;CBO.cur=o.current==null?'':o.current;CBO.on=true;
 cbo_q.value='';cbo_q.placeholder=o.placeholder||'Search…';cbo_q.setAttribute('aria-label',o.label||'Search');cbo.setAttribute('aria-label',o.label||'Choose');
 const host=[...document.querySelectorAll('dialog[open]')].pop()||document.body;if(cbo.parentNode!==host)host.appendChild(cbo);   // inside an open modal, or the modal would make it inert
 if(CBP)cbo.showPopover();else cbo.classList.add('cbo-on');
 cboRender();cboPlace();cbo_l.scrollTop=0;cboActive(CBO.act,true);
 CBO.anchor.setAttribute('aria-expanded','true');
 cbo_q.focus({preventScroll:true})}
function cboSetItems(items,current){if(!CBO.on)return;const v=CBO.vis[CBO.act]&&CBO.vis[CBO.act].v;CBO.items=items;CBO.cur=current==null?'':current;const st=cbo_l.scrollTop;cboRender(v);cboPlace();cbo_l.scrollTop=st}
function cboClose(quiet){
 if(!CBO.on)return;CBO.on=false;const a=CBO.anchor,o=CBO.o;
 if(CBP){try{cbo.hidePopover()}catch(e){}}else cbo.classList.remove('cbo-on');
 a&&a.setAttribute('aria-expanded','false');
 o&&o.onClose&&o.onClose();
 if(!quiet&&a&&a.isConnected)a.focus({preventScroll:true})}
function cboChoose(n){const it=CBO.vis[n];if(!it||it.dis)return;const o=CBO.o;cboClose();o.onChoose&&o.onChoose(it)}
cbo_q.addEventListener('input',()=>{if(CBO.on){cboRender();cboPlace()}});
cbo_q.addEventListener('keydown',e=>{if(!CBO.on)return;const k=e.key;
 if(k==='ArrowDown'||k==='ArrowUp'){e.preventDefault();cboMove(k==='ArrowDown'?1:-1)}
 else if(k==='PageDown'||k==='PageUp'){e.preventDefault();for(let i=0;i<7;i++)cboMove(k==='PageDown'?1:-1)}
 else if(k==='Home'||k==='End'){e.preventDefault();cboMove(0,k==='Home'?1:-1)}
 else if(k==='Enter'){e.preventDefault();if(CBO.act>=0)cboChoose(CBO.act)}
 else if(k==='Escape'){e.preventDefault();e.stopPropagation();cboClose()}
 else if(k==='Tab')cboClose()});
cbo_l.addEventListener('pointerdown',e=>e.preventDefault());
cbo_l.addEventListener('click',e=>{const r=e.target.closest('[data-n]');if(r)cboChoose(+r.dataset.n)});
cbo_l.addEventListener('mousemove',e=>{const r=e.target.closest('[data-n]');if(r&&+r.dataset.n!==CBO.act&&!r.matches('[aria-disabled=true]'))cboActive(+r.dataset.n,false)});
document.addEventListener('pointerdown',e=>{if(CBO.on&&!cbo.contains(e.target)&&!(CBO.anchor&&CBO.anchor.contains(e.target)))cboClose(true)},true);
window.addEventListener('scroll',cboFollow,true);window.addEventListener('resize',()=>cboFollow());try{visualViewport.addEventListener('resize',()=>cboFollow());visualViewport.addEventListener('scroll',()=>cboFollow())}catch(e){}
document.addEventListener('close',e=>{if(CBO.on&&e.target.tagName==='DIALOG')cboClose(true)},true);
function cbSync(sel){
 const b=sel._cb;if(!b)return;const o=sel.selectedOptions[0];
 b.firstChild.textContent=o?o.textContent:'';b.classList.toggle('bad',sel.classList.contains('bad'));
 const h=sel.title||(sel.closest('[title]')||{}).title||'',raw=o&&o.dataset.raw&&o.dataset.raw!==o.textContent?' ('+o.dataset.raw+')':'',n=o&&sel.dataset.cbdev!==undefined?o.textContent+raw:'';b.title=n&&h?n+'\n'+h:n||h;
 if(sel._out){const t=(sel._outl||'Output')+(o&&o.textContent?': '+o.textContent+raw:'');sel._out.title=t;sel._out.setAttribute('aria-label',t)}}   // the speaker button of this output names the chosen device
function cbItems(sel){
 const pin=sel.dataset.cbpin,seen=new Set();
 return [...sel.options].map(o=>({v:o.value,t:o.textContent,dis:o.disabled,g:o.dataset.g||'',hid:o.dataset.hid==='1',title:o.dataset.raw&&o.dataset.raw!==o.textContent?o.textContent+'\n'+o.dataset.raw:'',k:o.dataset.raw&&o.dataset.raw!==o.textContent?o.textContent+' '+o.dataset.raw:'',pin:pin!==undefined&&o.value===pin&&!seen.has(o.value)&&seen.add(o.value)}))}
function cbOpenSel(sel,anchor){
 const b=anchor||sel._cb;if(CBO.on&&CBO.anchor===b){cboClose();return}
 const lab=(document.querySelector(`label[for="${sel.id}"],label[for="${sel.id}_cb"]`)||sel.closest('label')||{}).textContent||sel.getAttribute('aria-label')||'';
 cboOpen({anchor:b,items:cbItems(sel),current:sel.value,label:lab.trim()||sel.id,placeholder:sel.dataset.cbdev!==undefined?'Search devices…':'Search…',empty:sel.dataset.cbdev!==undefined?'No devices match':'No match',
  onChoose:it=>{if(sel.value!==it.v||!sel.selectedOptions[0]){sel.value=it.v;cbSync(sel);sel.dispatchEvent(new Event('change',{bubbles:true}))}}});
 if(sel.dataset.cbdev!==undefined)loadDevs().then(()=>{if(CBO.on&&CBO.anchor===b)cboSetItems(cbItems(sel),sel.value)}).catch(()=>{})}
function cbEnhance(sel){
 if(sel._cb)return;
 const b=document.createElement('button');b.type='button';b.className='cbtn '+sel.className.replace(/\bcbsel\b/,'');b.id=sel.id+'_cb';
 b.setAttribute('role','combobox');b.setAttribute('aria-haspopup','listbox');b.setAttribute('aria-expanded','false');b.setAttribute('aria-controls','cbo_l');
 b.appendChild(document.createElement('span'));
 const l=sel.getAttribute('aria-label')||(document.querySelector(`label[for="${sel.id}"]`)||sel.closest('label')||{}).textContent;if(l)b.setAttribute('aria-label',l.trim());
 sel.before(b);sel._cb=b;sel.classList.add('cbsel');sel.tabIndex=-1;sel.setAttribute('aria-hidden','true');
 document.querySelectorAll(`label[for="${sel.id}"]`).forEach(x=>x.setAttribute('for',b.id));
 b.addEventListener('click',()=>cbOpenSel(sel));
 b.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!(CBO.on&&CBO.anchor===b))cbOpenSel(sel)}});
 new MutationObserver(()=>cbSync(sel)).observe(sel,{childList:true,attributes:true,attributeFilter:['class','title']});
 sel.addEventListener('change',()=>cbSync(sel));cbSync(sel)}
/* Output lists. The option VALUE is the exact device name from the player (SDL names can hold double spaces, e.g.
   'DVS Transmit  1-2 (Dante Virtual Soundcard)', and an option without a value would send the collapsed text); the
   text may differ (a ' (2)' suffix for a repeated name). Selection is by exact string only. */
let OUTI={},SHOWHID=false;try{SHOWHID=localStorage.getItem('cp_show_hidden_out')==='1'}catch(e){}
/* Output aliases (output_info of /api/devices): the menu shows the label, the value stays the raw name. menu = live | preview | mirror.
   A hidden output is listed only when it is the current choice or "Show hidden outputs" is on (then dimmed, with the word hidden);
   a live-only output (Dante over IP) is offered in the Live menu only. A grouped output sits under its group heading, the rest under Wired. */
function devOpts(first,names,cur,menu){
 const seen={},wired=[],groups={};
 for(const n of names){const k=seen[n]=(seen[n]||0)+1,i=OUTI[n]||{label:n,hidden:false,group:'',live_only:false},isCur=n===cur;
  if(i.live_only&&menu!=='live'&&!isCur)continue;
  if(i.hidden&&!SHOWHID&&!isCur)continue;
  const lab=(i.label||n)+(k>1?' ('+k+')':'')+(i.hidden?' (hidden)':''),g=i.group||'Wired',
   o=`<option value="${escAttr(n)}" data-g="${escAttr(g)}" data-raw="${escAttr(n)}"${i.hidden?' data-hid=1':''}>${esc(lab)}</option>`;
  if(!i.group)wired.push(o);else(groups[g]=groups[g]||[]).push(o)}
 let h=`<option value="">${esc(first)}</option>`+wired.join('')+Object.values(groups).map(a=>a.join('')).join('');
 if(cur&&!names.includes(cur))h+=`<option value="${escAttr(cur)}" disabled>${esc(cur)} (not found)</option>`;
 return h}
function devSet(sel,first,names,cur,menu){const sig=JSON.stringify([first,names,cur||'',menu,OUTI,SHOWHID]);if(sel.dataset.sig!==sig){sel.dataset.sig=sig;sel.innerHTML=devOpts(first,names,cur,menu)}sel.value=cur||'';cbSync(sel)}
function devNote(){
 const n=DEVN||{};
 const t=[n.output,mlbl.hidden?'':n.mirror].filter(Boolean);
 devnote.hidden=!t.length;devnote.textContent=t.join(' ');
 if(window.set_devnote){set_devnote.hidden=!(n.output||n.preview||n.mirror);set_devnote.textContent=[n.output,n.preview,n.mirror].filter(Boolean).join(' ')}}
let DEVN={};
async function loadDevs(){
 const d=await j('/api/devices');
 OUTI={};for(const e of d.output_info||[])OUTI[e.name]=e;
 if(window.set_hidout)set_hidout.checked=SHOWHID;
 devSet(dev,'System default',d.devices,d.current||'','live');
 devSet(mdev,'Off',d.devices,d.mirror||'','mirror');
 mlbl.hidden=!d.mirror_enabled;if(window.set_mir)set_mir.checked=!!d.mirror_enabled;mdev.classList.toggle('bad',!!d.mirror_error);mdev.title=d.mirror_error||'';
 if(window.set_pv)devSet(set_pv,'Off',d.devices,d.preview||'','preview');
 if(window.set_mdev){devSet(set_mdev,'Off',d.devices,d.mirror||'','mirror');set_mdevrow.hidden=!d.mirror_enabled;set_mdev.classList.toggle('bad',!!d.mirror_error);set_mdev.title=d.mirror_error||'';cbSync(set_mdev)}
 INPD=d.inputs||[];inpDevSet(d.input||'');
 setSums();
 DEVN=d.notices||{};devNote();return d}
dev._out=dev_out;dev._outl='Live output';pvsel._out=pv_out;pvsel._outl='Preview plays on';
for(const e of [dev,mdev,set_pv,set_mdev,pvsel,set_pvt,inp_dev,set_inpdev,inp_ch,set_inpch])cbEnhance(e);
/* Live input (Duck only). The card in the Cue panel and the rows in Settings > Audio show one state (/api/state "input", level from the meter stream). */
let INP=null,INPD=null,inpTouch=0,inpErrT=0;
const INPMIN=-60;
function inpTog(open){const c=open===undefined?!inpc.classList.contains('ic'):!open;inpc.classList.toggle('ic',c);inp_ar.textContent=c?'▸':'▾';inp_t.setAttribute('aria-expanded',String(!c));try{localStorage.setItem('cp_inp',c?'0':'1')}catch(e){}}
try{if(localStorage.getItem('cp_inp')==='1')inpTog(true)}catch(e){}
const inpPct=db=>Math.max(0,Math.min(100,(db-INPMIN)/-INPMIN*100));
function inpLevels(lv,present){
 const ok=!!present&&Array.isArray(lv)&&lv.length>0,two=!!(INP&&INP.stereo),th=INP?INP.threshold_db:-30;
 inp_r2.hidden=!two;inp_bars.classList.toggle('two',two);
 const bars=[[inp_m,inp_lv],[inp_m2,inp_lv2]];let over=false;
 for(let k=0;k<(two?2:1);k++){const db=ok?lv[Math.min(k,lv.length-1)]:null,[m,f]=bars[k];
  f.style.width=(ok?inpPct(db):0)+'%';
  m.setAttribute('aria-valuenow',ok?Math.round(db):INPMIN);m.setAttribute('aria-valuetext',ok?db.toFixed(0)+' dB':'no input');m.classList.toggle('over',ok&&db>th);over=over||(ok&&db>th)}
 inpThrUi(over&&!!(INP&&INP.armed));
 inp_l1.textContent=two?'L':String(INP?INP.channel:1);
 inp_m.setAttribute('aria-label',two?'Left channel level in dB, after the input gain':'Input level in dB, after the input gain');
 inp_lvv.textContent=ok?Math.max(...lv).toFixed(0)+' dB':'-'}
/* The ducking threshold of the Live input (input_threshold_db, -60..0 dB, whole dB): the mark on the meter is a slider (drag, arrows, Home / End, double-click = reset),
   with a caption under the bars and a slider / number / Reset row in the open card and a number in Settings > Audio. THR.v is the value being set here; the answer of the
   player does not replace it while it is being dragged, while a save is in flight or for 1.5 s after the last edit (it would make the control jump back). */
const THR={v:-30,t:0,busy:false,dirty:false,drag:false,duck:false},THRMIN=-60,THRMAX=0;
const thrFmt=v=>(v<0?'\u2212':'')+Math.abs(v);
const thrHold=()=>THR.drag||THR.busy||THR.dirty||Date.now()-THR.t<1500;
function inpThrUi(duck){
 if(duck!==undefined)THR.duck=duck;
 const v=THR.v,def=INP&&INP.threshold_default!=null?INP.threshold_default:-30,ae=document.activeElement;
 inp_th.style.left=inpPct(v)+'%';
 inp_th.setAttribute('aria-valuenow',v);inp_th.setAttribute('aria-valuetext',thrFmt(v)+' dB');inp_th.classList.toggle('duck',THR.duck);
 const cap=THR.duck?'Ducking (above '+thrFmt(v)+' dB)':'Duck above '+thrFmt(v)+' dB';
 if(inp_thl.textContent!==cap)inp_thl.textContent=cap;
 inp_thl.classList.toggle('on',THR.duck);
 if(ae!==inp_thr)inp_thr.value=v;
 for(const e of [inp_thn,set_inpthr])if(ae!==e)e.value=v;
 inp_thx.title='Back to the default ('+thrFmt(def)+' dB)';
 const tt='Where ducking starts. Drag it, click the bar, or use the arrow keys (1 dB, Shift 5 dB), Home and End. Double-click to go back to the default ('+thrFmt(def)+' dB).';if(inp_th.title!==tt)inp_th.title=tt}
async function inpThrSend(){
 if(THR.busy){THR.dirty=true;return}
 THR.busy=true;THR.dirty=false;const v=THR.v;
 const ok=await inpSave({threshold_db:v});
 THR.busy=false;if(!ok){THR.t=0;THR.dirty=false;THR.drag=false;inp_th.classList.remove('drag')}
 else if(THR.dirty||THR.v!==v)inpThrSend()}
function inpThrApply(db,fromBox){
 if(!isFinite(db)){for(const e of [inp_thn,set_inpthr])e.value=THR.v;inpThrUi();return}
 const v=Math.max(THRMIN,Math.min(THRMAX,Math.round(db)));
 THR.v=v;THR.t=Date.now();if(INP)INP.threshold_db=v;
 if(fromBox){inp_thn.value=v;set_inpthr.value=v}
 inpThrUi();inpThrSend()}
const inpThrReset=()=>inpThrApply(INP&&INP.threshold_default!=null?INP.threshold_default:-30,true);
let THRDX=0;
function inpThrAt(ev){const r=inp_thw.getBoundingClientRect();return INPMIN+(ev.clientX-THRDX-r.left)/Math.max(1,r.width)*-INPMIN}
inp_th.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();inp_th.setPointerCapture(e.pointerId);{const r=inp_th.getBoundingClientRect();THRDX=e.clientX-(r.left+r.width/2)}THR.drag=true;inp_th.classList.add('drag');inp_th.focus({preventScroll:true})});
inp_th.addEventListener('pointermove',e=>{if(THR.drag)inpThrApply(inpThrAt(e))});
const inpThrEnd=e=>{if(!THR.drag)return;THR.drag=false;inp_th.classList.remove('drag');THR.t=Date.now();inpThrSend()};
inp_th.addEventListener('pointerup',inpThrEnd);inp_th.addEventListener('pointercancel',inpThrEnd);inp_th.addEventListener('lostpointercapture',inpThrEnd);
inp_th.addEventListener('dblclick',e=>{e.preventDefault();inpThrReset()});
/* a click (or a press and drag) on the bars moves the mark there; a press on the L / R label does nothing */
inp_bars.addEventListener('pointerdown',e=>{
 if(e.button!==0||e.target.closest('#inp_th')||e.clientX<inp_thw.getBoundingClientRect().left)return;
 e.preventDefault();THRDX=0;inp_th.setPointerCapture(e.pointerId);THR.drag=true;inp_th.classList.add('drag');inp_th.focus({preventScroll:true});inpThrApply(inpThrAt(e))});
inp_th.addEventListener('keydown',e=>{
 const k=e.key,st=e.shiftKey?5:1;let v=null;
 if(k==='ArrowLeft'||k==='ArrowDown')v=THR.v-st;else if(k==='ArrowRight'||k==='ArrowUp')v=THR.v+st;
 else if(k==='PageDown')v=THR.v-5;else if(k==='PageUp')v=THR.v+5;else if(k==='Home')v=THRMIN;else if(k==='End')v=THRMAX;
 if(v===null||e.altKey||e.ctrlKey||e.metaKey)return;e.preventDefault();inpThrApply(v)});
/* The Cue container shows the armed state of the input (only while a capture device is chosen): a status line instead of "No cue" (armed), under it (off), a pill in the header (a cue is loaded). */
function cueIn(){
 const fs=document.getElementById('fs');if(!fs)return;
 const i=INP,on=!!(i&&i.device),cue=!!(LASTS&&LASTS.focus_name&&LASTS.focus_name!=='-');
 if(!on){cue_ia.hidden=true;cue_pill.hidden=true;fs.classList.remove('arm-a');return}
 const armed=!!i.armed,live=!!i.present,lab=i.channel_label,st=!armed?'off':live?'on':'warn';
 const nm=armed?'Input armed. Switch off to disarm':'Input armed. Switch on to arm';
 const why=i.switching?'Switching the input…':(/not found/.test(i.reason||'')?i.device+' not found. Ducking is off until it returns.':((i.reason||'No input')+(/[.…]$/.test(i.reason||'')?'':'.')+' Ducking is off until it returns.'));
 cue_pill.hidden=!cue;cue_ia.hidden=cue;fs.classList.toggle('arm-a',!cue&&armed);
 if(cue){cue_pill.dataset.st=st;cue_pill_t.textContent=!armed?'Input off':live?'Input armed':'Input armed, no input';
  cue_pill_sw.setAttribute('aria-pressed',String(armed));cue_pill_sw.setAttribute('aria-label',nm)}
 else{cue_ia.dataset.st=st;cia_h.textContent=!armed?'Input off':live?'Input armed':'Input armed, no input';
  cia_s.textContent=!armed?'Voice ducking from '+lab+' is not active':live?'Ducking when '+lab+' hears speech':why;
  const chip=!armed?'':live?(i.signal?'Signal present':''):i.chip;cia_chip.hidden=!chip;cia_chip.textContent=chip;cia_chip.className='inpchip '+(live?'sig':'off');
  cia_sw.setAttribute('aria-pressed',String(armed));cia_sw.setAttribute('aria-label',nm)}}
/* the one-line summary: "ducking -N dB" while the input ducks (fed by the meter stream, 14 times a second), else armed / not armed */
let INPBASE='';
let INPDN=false;
function inpGr(g){const on=g>0.5;inp_sum.textContent=INPDN?'DUCK NOW'+(on?' · -'+Math.round(g)+' dB':''):on?'ducking -'+Math.round(g)+' dB':INPBASE;inp_sum.classList.toggle('on',on||INPDN)}
function inpDevSet(cur){const names=INPD||(cur?[cur]:[]);for(const sel of [inp_dev,set_inpdev])devSet(sel,'No input',names,cur)}
function inpGainInfo(){inp_gain_v.textContent=(+inp_gain.value>0?'+':'')+(+inp_gain.value).toFixed(1)+' dB'}
function inpChOpts(sel,i){const sig=JSON.stringify(i.choices.map(c=>[c.v,c.label]));
 if(sel.dataset.sig!==sig){sel.dataset.sig=sig;sel.innerHTML=i.choices.map(c=>`<option value="${c.v}" data-g="${c.group}">${esc(c.label)}</option>`).join('')}
 sel.value=i.channel_list.join('-');cbSync(sel)}
const inpChSave=v=>inpSave({channels:String(v).split('-').map(Number)});
const inpArmToggle=()=>inpSave({armed:!(INP&&INP.armed)});
function inpSync(i){
 INP=i;
 inp_chip.textContent=i.chip;inp_chip.className='inpchip '+(!i.present?'off':i.signal?'sig':'quiet');
 inp_chip.title=i.present?(i.signal?'The input has signal (above -60 dBFS within the last half second)':'The input is connected but silent'):(i.reason||'No input');
 inp_why.hidden=!i.reason;inp_why.textContent=i.reason||'';
 if(thrHold())i.threshold_db=THR.v;else THR.v=i.threshold_db;
 inpLevels(i.levels_db,i.present);
 const ae=document.activeElement;
 inp_arm.checked=!!i.armed;set_inparm.checked=!!i.armed;
 inp_dn.classList.toggle('on',!!i.duck_now);inp_dn.setAttribute('aria-pressed',String(!!i.duck_now));inp_dn.disabled=false;
 inp_so.classList.toggle('on',!!i.solo);inp_so.setAttribute('aria-pressed',String(!!i.solo));
 if(Date.now()-inpTouch>1500&&ae!==inp_gain&&ae!==set_inpgain){inp_gain.value=i.gain_db;set_inpgain.value=i.gain_db;inpGainInfo()}
 for(const sel of [inp_ch,set_inpch])if(!(CBO.on&&CBO.anchor===sel._cb))inpChOpts(sel,i)
 inpDevSet(i.device||'');
 INPDN=!!i.duck_now;INPBASE=i.device?(i.armed?'armed':'not armed'):'no device';inpGr(i.ducking?i.gr:0);
 const n=(DEVN&&DEVN.input)||'';set_inpnote.hidden=!(n||i.reason||i.note);set_inpnote.textContent=[n,i.note,i.reason].filter(Boolean).join(' ');inp_note.hidden=!i.note;inp_note.textContent=i.note||'';cueIn();
 setSums()}
function inpErr(t){inp_err.hidden=!t;inp_err.textContent=t||'';clearTimeout(inpErrT);if(t)inpErrT=setTimeout(()=>inpErr(''),6000)}
async function inpCall(url,body){
 inpTouch=Date.now();
 try{const r=await fetch(url,{method:'POST',body:JSON.stringify(body)});const d=await r.json();
  if(!r.ok){inpErr(d.error||'That did not work');say(d.error||'That did not work',false);inpTouch=0;await render();return false}      // the fields go back to what the player holds
  inpErr('');inpTouch=0;inpSync(d);return true}
 catch(e){inpErr('The player did not answer');return false}}
const inpSave=p=>inpCall('/api/input',p);
const inpDuckNow=()=>inpCall('/api/input/ducknow',{on:!(INP&&INP.duck_now)});
const inpSolo=()=>inpCall('/api/input/solo',{on:!(INP&&INP.solo)});
async function setMirrorOn(on){
 await fetch('/api/mirror/enable',{method:'POST',body:JSON.stringify({on})});
 await loadDevs()
}
async function setMirrorDev(v){mdev.value=v;cbSync(mdev);await setmirror()}
async function setmirror(){
 const r=await fetch('/api/mirror/device',{method:'POST',body:JSON.stringify({name:mdev.value||null})});
 if(!r.ok){const e=await r.json().catch(()=>({}));alert(e.error||'Could not use that device');loadDevs();return}
 setTimeout(loadDevs,1200)
}
async function setdev(){
 const r=await fetch('/api/device',{method:'POST',body:JSON.stringify({name:dev.value||null})});
 if(!r.ok)alert('Could not open that output');
 loadDevs();render();
}

let pickTarget=null;
function pick(i){pickTarget=i;picker.value='';picker.click()}
picker.onchange=()=>uploadFiles(pickTarget,[...picker.files]);
picker2.onchange=()=>{const base='';uploadItems(pickTarget,[...picker2.files].map(f=>({f,folder:joinF(base,dirOf(f.webkitRelativePath||'')),dir:true})))};
function upMenu(btn){let m=document.getElementById('upmenu');if(m){m.remove();return}
 m=document.createElement('div');m.id='upmenu';m.className='upmenu';
 m.innerHTML='<button data-k=f>Files…</button><button data-k=d>Folder…</button><small>Tip: you can drag files and folders onto the library together.</small>';
 const r=btn.getBoundingClientRect();m.style.top=(r.bottom+4)+'px';m.style.left=Math.max(8,Math.min(r.left,innerWidth-230))+'px';
 document.body.appendChild(m);
 m.onclick=e=>{const k=e.target.dataset&&e.target.dataset.k;if(!k)return;m.remove();pickTarget=null;if(k==='f'){picker.value='';picker.click()}else{picker2.value='';picker2.click()}};
 const off=ev=>{if(!m.contains(ev.target)||ev.target===document.body){m.remove()}document.removeEventListener('click',off,true)};
 setTimeout(()=>document.addEventListener('click',off,true),0)}
/* folders: every folder dropped or chosen becomes a real library folder (nested folders are kept); only audio files go in */
const AUDIO_RE=/\.(wav|mp3|ogg|flac|m4a|aac|aif|aiff|aifc|caf|wma|opus|oga|mp2|ac3|wv|mp4|m4v|mov|mkv|webm|avi|3gp)$/i;   // the others need ffmpeg on the player
const cleanSeg=x=>String(x).replace(/[^\w.\- ]/g,'_').replace(/\s+/g,' ').trim().replace(/^[._]+/,'').slice(0,120);
const joinF=(a,b)=>[a,b].filter(Boolean).join('/');
const dirOf=pth=>{const q=String(pth).split('/');q.pop();return q.join('/')};
function dropSnap(e){const dt=e.dataTransfer;const ents=[...(dt.items||[])].filter(i=>i.kind==='file').map(i=>i.webkitGetAsEntry?i.webkitGetAsEntry():null);
 return {ents:ents.length&&ents.every(Boolean)?ents:null,files:[...dt.files]}}
async function walkEntry(ent,prefix,out){
 if(ent.isFile){const f=await new Promise(r=>ent.file(r,()=>r(null)));if(f)out.push({f,folder:prefix,dir:!!prefix});return}
 if(!ent.isDirectory||ent.name.startsWith('.'))return;
 const p=joinF(prefix,ent.name),rd=ent.createReader();
 for(;;){const kids=await new Promise(r=>rd.readEntries(r,()=>r([])));if(!kids.length)break;for(const k of kids)await walkEntry(k,p,out)}}
async function uploadSnap(pl,snap,base){
 const out=[];
 if(snap.ents){for(const ent of snap.ents){if(ent.isDirectory){await walkEntry(ent,base||'',out)}else{const f=await new Promise(r=>ent.file(r,()=>r(null)));if(f)out.push({f,folder:base||'',dir:false})}}}
 else for(const f of snap.files)out.push({f,folder:base||'',dir:false});
 uploadItems(pl,out)}
const plOf=e=>e.target.closest&&e.target.closest('.pl');
const isFiles=e=>e.dataTransfer&&[...e.dataTransfer.types].includes('Files');
const clearMarks=()=>document.querySelectorAll('.dropbefore,.dropafter,.dropt,.drop,.over,.plbefore,.plafter,.fdover').forEach(x=>x.classList.remove('dropbefore','dropafter','dropt','drop','over','plbefore','plafter','fdover'));
['dragover','drop'].forEach(t=>window.addEventListener(t,e=>e.preventDefault()));   // never let the browser open dropped files
document.addEventListener('dragstart',e=>{
 const pg=e.target.closest&&e.target.closest('.plgrip');
 if(pg){const c=pg.closest('.pl');dragging={pl:+c.dataset.i};e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain','playlist');
  try{e.dataTransfer.setDragImage(c,24,16)}catch(_){}return}
 const li=e.target.closest&&e.target.closest('li.t'),lt=e.target.closest&&e.target.closest('.lt');
 const fdr=e.target.closest&&e.target.closest('.fd[data-path]:not(.rootdrop)');
 if(li)dragging={i:+li.dataset.i,k:+li.dataset.k};
 else if(lt){const id=lt.dataset.id,ids=SEL.has(id)&&SEL.size>1?libOrder().filter(x=>SEL.has(x)):[id];dragging={lib:id,ids};setTimeout(()=>{if(dragging)lib.classList.add('dragmode')},0)}
 else if(fdr&&fdr.dataset.path){const path=fdr.dataset.path,ids=LIBF.filter(x=>x.id.startsWith(path+'/')).map(x=>x.id).sort(libCmp);
  if(!ids.length){e.preventDefault();return}dragging={lib:ids[0],ids,fdr:path}}
 else return;
 e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain','track')});
document.addEventListener('dragend',()=>{dragging=null;lib.classList.remove('dragmode');clearMarks()});
lib.addEventListener('dragover',e=>{const fd=e.target.closest('.fd');if(!fd)return;
 if((dragging&&dragging.lib!==undefined&&!dragging.fdr)||isFiles(e)){e.preventDefault();clearMarks();fd.classList.add('fdover')}});
lib.addEventListener('dragleave',e=>{const fd=e.target.closest('.fd');if(fd&&!fd.contains(e.relatedTarget))fd.classList.remove('fdover')});
lib.addEventListener('drop',e=>{const fd=e.target.closest('.fd');if(!fd)return;fd.classList.remove('fdover');lib.classList.remove('dragmode');
 if(isFiles(e)){uploadSnap(null,dropSnap(e),fd.dataset.path);return}
 if(dragging&&dragging.lib!==undefined&&!dragging.fdr){const ids=dragging.ids||[dragging.lib];dragging=null;(async()=>{for(const id of ids)await moveToFolder(id,fd.dataset.path);if(SEL.size)selClear()})()}});
const NEWZ='.emptydrop,.newdrop';
plcol.addEventListener('dragover',e=>{const ed=e.target.closest(NEWZ);
 if(ed&&((dragging&&dragging.lib!==undefined)||isFiles(e))){e.preventDefault();ed.classList.add('drop')}});
plcol.addEventListener('dragleave',e=>{const ed=e.target.closest(NEWZ);if(ed&&!ed.contains(e.relatedTarget))ed.classList.remove('drop')});
plcol.addEventListener('drop',async e=>{
 const ed=e.target.closest(NEWZ);if(!ed)return;e.preventDefault();ed.classList.remove('drop');
 const files=isFiles(e)?dropSnap(e):null,src=dragging;dragging=null;lib.classList.remove('dragmode');
 if(!files&&!(src&&src.lib!==undefined))return;
 const ids=src?(src.ids||[src.lib]):[];
 const name=src&&src.fdr?src.fdr.slice(src.fdr.lastIndexOf('/')+1):(ids.length===1?((LIBF.find(x=>x.id===ids[0])||{}).name):'')||'Untitled playlist';
 await fetch('/api/playlists',{method:'POST',body:JSON.stringify({name})});
 PL=await j('/api/playlists');const n=PL.length-1;
 if(files)uploadSnap(n,files);else await addToPl(n,ids,1e9);
 if(SEL.size)selClear();lastHtml='';await render(true);
 plChip('Created playlist',files?'':ids.length?' with '+ids.length+(ids.length===1?' track':' tracks'):'')});
libcol.addEventListener('dragover',e=>{if(isFiles(e)){e.preventDefault();if(!e.target.closest('.fd'))libcol.classList.add('over')}else libcol.classList.remove('over')});
libcol.addEventListener('dragleave',e=>{if(!libcol.contains(e.relatedTarget))libcol.classList.remove('over')});
libcol.addEventListener('drop',e=>{libcol.classList.remove('over');if(isFiles(e)&&!e.target.closest('.fd')){e.preventDefault();uploadSnap(null,dropSnap(e))}});
lists.addEventListener('dragover',e=>{
 const pl=plOf(e);if(!pl)return;
 if(dragging&&dragging.pl!==undefined){clearMarks();const r=pl.getBoundingClientRect();pl.classList.add(e.clientY<r.top+r.height/2?'plbefore':'plafter');return}
 if(dragging&&!isFiles(e)){
  clearMarks();const li=e.target.closest('li.t');
  if(li){const r=li.getBoundingClientRect();li.classList.add(e.clientY<r.top+r.height/2?'dropbefore':'dropafter')}
  else pl.classList.add('dropt');
  return}
 pl.classList.add('drop')});
lists.addEventListener('dragleave',e=>{const pl=plOf(e);if(pl&&!pl.contains(e.relatedTarget))clearMarks()});
lists.addEventListener('drop',e=>{
 const pl=plOf(e);if(!pl)return;
 if(dragging&&dragging.pl!==undefined){
  const src=dragging.pl,r=pl.getBoundingClientRect();let to=+pl.dataset.i+(e.clientY<r.top+r.height/2?0:1);
  if(to>src)to-=1;dragging=null;clearMarks();movePl(src,to);return}
 if(dragging&&!isFiles(e)){
  const src=dragging,li=e.target.closest('li.t'),tp=+pl.dataset.i;let ti=1e9;
  dragging=null;
  if(li){const k=+li.dataset.k,r=li.getBoundingClientRect();ti=e.clientY<r.top+r.height/2?k:k+1;
   if(src.lib===undefined&&tp===src.i&&ti>src.k)ti-=1}        // a dragged row leaves its old spot first
  clearMarks();
  if(src.lib!==undefined){addToPl(tp,src.ids||[src.lib],ti);if(SEL.size)selClear()}else mv(src.i,src.k,tp,ti);
  return}
 clearMarks();uploadSnap(+pl.dataset.i,dropSnap(e))});

let UPL=[],upid=0;
function upRows(){return UPL.map(u=>`<div class="lt upl${u.err?' err':''}" data-uid=${u.id} ${u.err?'title="Click to dismiss"':''}><span class=grip>⇪</span><span class=ln>${esc(u.name)}${u.folder?` <small class=dim>${esc(u.folder)}</small>`:''}</span>
  <span class=upb>${u.err?`<em>${esc(u.msg)}</em>`:`<progress max=100 value=${u.pc}></progress><em>${esc(u.msg)}</em>`}</span></div>`).join('')}
function upDone(u,ms){setTimeout(()=>{UPL=UPL.filter(x=>x!==u);lastLib='';renderLib()},ms)}
lib.addEventListener('click',e=>{const r=e.target.closest('.lt.upl.err');if(r){UPL=UPL.filter(x=>String(x.id)!==r.dataset.uid);lastLib='';renderLib()}});
function uploadFiles(pl,files,folder){return uploadItems(pl,files.map(f=>({f,folder:folder||'',dir:false})))}
async function uploadItems(pl,list){
 // loose files keep the order they were given; files that came out of folders follow, sorted by folder and name
 const cmp=(a,b)=>(a.folder+'/'+a.f.name).localeCompare(b.folder+'/'+b.f.name,undefined,{numeric:true,sensitivity:'base'});
 let skipped=0;const loose=[],deep=[];
 for(const o of list){
  const segs=String(o.folder).split('/').filter(Boolean);
  if(segs.some(x=>x.startsWith('.'))||o.f.name.startsWith('.')){skipped++;continue}
  const clean=segs.map(cleanSeg);if(clean.some(x=>!x)){skipped++;continue}
  const it={f:o.f,folder:clean.join('/'),dir:o.dir};
  if(o.dir){if(AUDIO_RE.test(o.f.name))deep.push(it);else skipped++}else loose.push(it)}
 deep.sort(cmp);
 const items0=[...loose,...deep];
 if(!items0.length){if(skipped)alert('No audio files found. Only wav, mp3, ogg and flac files are uploaded.');return}
 const items=items0.map(o=>({id:++upid,name:o.f.name,folder:o.folder,pc:0,msg:'waiting',err:false,f:o.f}));
 UPL.push(...items);lastLib='';renderLib();
 for(const u of items){                       // one at a time, so tracks land in the order they were dropped
  await new Promise(done=>{
   const el=()=>lib.querySelector(`.lt.upl[data-uid="${u.id}"]`);
   const x=new XMLHttpRequest();const qs=new URLSearchParams();if(pl!==null&&pl!==undefined)qs.set('playlist',pl);if(u.folder)qs.set('folder',u.folder);
   x.open('POST','/api/library/upload'+(qs.toString()?'?'+qs:''));
   x.upload.onprogress=e=>{if(e.lengthComputable){u.pc=Math.round(e.loaded/e.total*100);u.msg=u.pc>=100?'processing…':u.pc+'%';const r=el();if(r){r.querySelector('progress').value=u.pc;r.querySelector('em').textContent=u.msg}}};
   x.onload=()=>{
    if(x.status===200){let dup=false;try{dup=JSON.parse(x.responseText).files[0].duplicate}catch(_){}
     if(dup){u.pc=100;u.msg='already in library';upDone(u,4000)}else{UPL=UPL.filter(z=>z!==u)}}
    else{let m=String(x.status);try{m=JSON.parse(x.responseText).error||m}catch(_){}u.err=true;u.msg=m;upDone(u,15000)}
    lastLib='';renderLib();render(true);done()};
   x.onerror=()=>{u.err=true;u.msg='upload failed';lastLib='';renderLib();upDone(u,15000);done()};
   const fd=new FormData();fd.append('file',u.f,u.name);x.send(fd);
  });
 }
}
const MEL={};
function meterFrame(m){
  try{
   const lv=pvt()==='browser'?(bsolo?soloLevels(m):localLevels()):null;
   for(const k of ['live','preview'])for(const c of ['l','r']){const id='m_'+k+'_'+c;let e=MEL[id];if(!e||!e.isConnected)e=MEL[id]=document.getElementById(id);
    const cov=(100-((k==='preview'&&pvMuted)?0:(k==='preview'&&lv)?lv[c==='l'?0:1]:m[k][c])).toFixed(1)+'%';      // the cover above the level (a muted preview output reads empty)
    if(e)e.style.height=cov;
    const hid='h_'+k+'_'+c;let he=MEL[hid];if(!he||!he.isConnected)he=MEL[hid]=document.getElementById(hid);if(he)he.style.width=cov}      // the one-line panel's horizontal pair
   {if(m.input){if(INP)INP.stereo=m.input.stereo;inpLevels(m.input.levels_db,m.input.present);inpGr(m.in_gr||0)}const g=Math.max(0,(m.gr||0)+(m.in_gr||0));dk_gr.style.setProperty('--gr',Math.min(100,g/GRMAX*100)+'%');dk_grv.textContent='-'+g.toFixed(1)+' dB';dk_grm.classList.toggle('duck',g>0.05);if(g>0.5){duck_sum.textContent='ducking -'+g.toFixed(0)+' dB';duck_sum.classList.add('on');duck_sum._on=1}else if(duck_sum._on){duck_sum._on=0;duck_sum.classList.remove('on');dkInfo()}}
   lvl.title=m.enabled?'Live level':'Level meters need numpy (pip install numpy)'}catch(e){}
}
/* one server-sent stream carries the meters and the preview output's state; it is closed while the tab is hidden */
let LIVEES=null;
function liveOpen(){
 if(LIVEES||document.hidden||!window.EventSource)return;
 const es=LIVEES=new EventSource('/api/live');
 es.onmessage=ev=>{try{const d=JSON.parse(ev.data);meterFrame(d.m);
  if(d.pv&&PVDEV&&pvt()!=='browser'){renderPv(d.pv);if(pvt()==='both')bothSync(d.pv)}}catch(e){}};
 es.onerror=()=>{if(es.readyState===2){LIVEES=null;setTimeout(liveOpen,3000)}}}   // refused: try again; otherwise the browser reconnects by itself
function liveClose(){if(LIVEES){LIVEES.close();LIVEES=null}}
document.addEventListener('visibilitychange',()=>document.hidden?liveClose():liveOpen());
syncLook();/* ---- waveforms (optional, Settings > Appearance): live and preview, click or drag to seek ---- */
let _c={t:-1e9};
function cols(){const n=performance.now();if(n-_c.t>400){const s=getComputedStyle(document.documentElement),g=k=>s.getPropertyValue(k).trim();
 _c={t:n,live:g('--live'),pv:g('--pv'),dim:g('--dim'),text:g('--text'),trg:g('--trg')||'#7c3aed'}}return _c}
function waveFor(fid){
 if(!fid)return null;
 if(!WF[fid]){WF[fid]={peaks:[],dur:0,loading:true};
  j('/api/waveform?id='+encodeURIComponent(fid)).then(w=>{WF[fid]=w.peaks?w:{peaks:[],dur:0,failed:true}}).catch(()=>{WF[fid]={peaks:[],dur:0,failed:true}})}
 return WF[fid]}
const RMQ=window.matchMedia?matchMedia('(prefers-reduced-motion: reduce)'):null;
/* style 'classic' (live): played in full colour, unplayed in the dim colour, a 2px playhead line.
   style 'bar' (preview): a progress fill, the played part full, the unplayed part the same colour at low alpha, no playhead line.
   busy (bar only, while the waveform or the preview is still loading): a flat low placeholder bar pattern with a soft band sweeping across
   (nothing reports real progress, so it is indeterminate); a static dimmed placeholder with prefers-reduced-motion. */
function drawWave(cv,w,frac,played,msg,rng,style,busy,ts){
 const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;if(!W||!H)return;
 if(cv.width!==Math.round(W*dpr)||cv.height!==Math.round(H*dpr)){cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr)}
const x=cv.getContext('2d'),c=cols();x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,W,H);
 const bar=style==='bar';
 if(bar&&busy&&(!w||!w.peaks.length)){
  const n=Math.max(8,Math.floor(W/4)),bw=W/n,still=RMQ&&RMQ.matches,pos=still?-1:((ts||0)/1500)%1.6-.3,wd=.28;
  for(let i=0;i<n;i++){const h=H*(.12+.1*(((i*7919)%13)/13)),u=(i+.5)/n,b=still?0:Math.max(0,1-Math.abs(u-pos)/wd);
   x.globalAlpha=.22+.78*b*b*(3-2*b);x.fillStyle=played;x.fillRect(i*bw,(H-h)/2,Math.max(1,bw-1),h)}
  x.globalAlpha=1;return}
 if(!w||!w.peaks.length){x.globalAlpha=.5;x.fillStyle=c.dim;x.fillRect(0,H/2-1,W,2);x.globalAlpha=1;
  x.font='12px system-ui,sans-serif';x.textBaseline='middle';x.fillText(msg||'',10,H/2-13);return}
 const n=w.peaks.length,bw=W/n;
 for(let i=0;i<n;i++){const h=Math.max(2,w.peaks[i]/255*(H-6)),on=(i+.5)/n<=frac;
  const out=rng&&((i+.5)/n<rng[0]||(i+.5)/n>rng[1]);
  const pl=(on||frac<0)&&!out;
  x.globalAlpha=out?.16:pl?1:bar?.26:.45;x.fillStyle=out?c.dim:(pl||bar)?played:c.dim;x.fillRect(i*bw,(H-h)/2,Math.max(1,bw-.8),h)}
 if(rng){x.globalAlpha=.9;x.fillStyle='#2fa84f';if(rng[0]>0.001)x.fillRect(Math.max(0,rng[0]*W-1),0,2,H);x.fillStyle='#e5484d';if(rng[1]<.999)x.fillRect(Math.min(W-2,rng[1]*W-1),0,2,H)}
x.globalAlpha=1;if(frac>=0&&!bar){x.fillStyle=c.text;x.fillRect(Math.min(W-2,Math.max(0,frac*W-1)),0,2,H)}}
const rngOf=(lo,hi,dur)=>dur>0&&(lo>0.01||hi<dur-0.01)&&hi>lo?[lo/dur,hi/dur]:null;
const wmsg=(w,none)=>w?(w.loading?'Analyzing waveform…':w.failed?'no waveform available':''):none;
function pvPosDur(){
 if(pvt()==='browser')return [AU.currentTime||0,isFinite(AU.duration)?AU.duration:((waveFor(PVCUR.id)||{}).dur||0)];
 return [PVST.pos+(PVST.state==='playing'?(performance.now()-PVST.t0)/1000:0),PVST.dur]}
let wfT=0;
function waveLoop(ts){
 requestAnimationFrame(waveLoop);
 if(document.hidden||ts-wfT<33)return;
 trgTick();
 if(TR&&trdlg.open){trDraw();trIcons()}
 if(!WAVE){return}wfT=ts;
 const lw=LIVE.fid?waveFor(LIVE.fid):null,ld=LIVE.dur||(lw&&lw.dur)||0;
 const lpos=scrub&&scrub.cv===wfl?scrub.pos:(LIVE.playing?LIVE.pos+(performance.now()-LIVE.t0)/1000:LIVE.pos);
 if(window.ms_prog)ms_prog.style.width=(ld?Math.min(1,lpos/ld)*100:0).toFixed(1)+'%';
 drawWave(wfl,lw,ld?Math.min(1,lpos/ld):0,cols().live,wmsg(lw,'Nothing live'),rngOf(LIVE.lo,LIVE.hi,ld));trgFlags(wfl,ld);
 if(pv.classList.contains('on')){
  const pw=PVCUR.id?waveFor(PVCUR.id):null;let [pp,pd]=scrub&&scrub.cv===wfp?[scrub.pos,scrub.dur]:pvPosDur();pd=pd||(pw&&pw.dur)||0;
  const busy=!!PVCUR.id&&(!pw||pw.loading||(PVCUR.state==='loading'&&!pw.peaks.length));
  drawWave(wfp,pw,pd?Math.min(1,pp/pd):0,cols().pv,wmsg(pw,'Nothing cued'),PVTRIM?rngOf(PVTRIM.in||0,PVTRIM.out!=null?PVTRIM.out:pd,pd):null,'bar',busy,ts)}}
requestAnimationFrame(waveLoop);
const clampLive=x=>LIVE.hi>LIVE.lo?Math.max(LIVE.lo,Math.min(x,Math.max(LIVE.lo,LIVE.hi-.3))):x;
function bindScrub(cv,kind){
 const frac=e=>{const r=cv.getBoundingClientRect();return Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))};
 cv.addEventListener('pointerdown',e=>{
  if(kind==='live'?!LIVE.fid:!PVCUR.id)return;
  const dur=kind==='live'?(LIVE.dur||(waveFor(LIVE.fid)||{}).dur||0):(pvPosDur()[1]||(waveFor(PVCUR.id)||{}).dur||0);
  if(!dur)return;scrub={cv,dur,pos:frac(e)*dur};if(kind==='live')scrub.pos=clampLive(scrub.pos);cv.setPointerCapture(e.pointerId);e.preventDefault()});
 cv.addEventListener('pointermove',e=>{if(scrub&&scrub.cv===cv)scrub.pos=kind==='live'?clampLive(frac(e)*scrub.dur):frac(e)*scrub.dur});
 cv.addEventListener('pointerup',()=>{if(!scrub||scrub.cv!==cv)return;const pos=scrub.pos;scrub=null;
  if(kind==='live'){LIVE.pos=pos;LIVE.t0=performance.now();fetch('/api/seek/'+pos.toFixed(2))}
  else{PVST.pos=pos;PVST.t0=performance.now();pvCtl('seek',{pos})}});
 cv.addEventListener('pointercancel',()=>{scrub=null})}
bindScrub(wfl,'live');bindScrub(wfp,'pv');
/* Solo live: hear what is on air. On the player's preview output it is done by the player; in this browser the page plays its own copy of the live tracks (the main output is not touched) */
let bsolo=false,LASTSOLO=false,monT=null;const MONA=new Map();
function soloUi(s){
 const mode=pvt(),on=mode==='pi'?LASTSOLO:mode==='browser'?bsolo:(bsolo||LASTSOLO);
 const where=mode==='pi'?'on the preview output':mode==='browser'?'in this browser':'on the preview output and in this browser';
 pvsolo.classList.toggle('on',on);pvsolo.disabled=mode==='pi'&&!s.preview.device;
 pvsolo.setAttribute('aria-pressed',on);
 pvsolo.title=on?'Live solo is ON: you hear the live audio '+where+'. The main output is not changed. Click to turn off.':'Solo live: hear the live audio '+where+'. The main output is not changed. The preview keeps playing, muted, until you turn this off.';
 pv.classList.toggle('solo',on);pvmSync();pvvl.textContent=on?'Solo vol':'Vol';pvvoll.title=on?'Solo live is on: this sets how loud the live audio is on the preview output':'Volume of the preview output';pvvol.setAttribute('aria-label',on?'Solo volume':'Preview volume')}
function monStop(){clearTimeout(monT);monT=null;for(const a of MONA.values()){a.pause();a.removeAttribute('src');a.load()}MONA.clear()}
async function monPoll(){
 clearTimeout(monT);if(!bsolo)return;
 try{const m=await j('/api/monitor'),now=performance.now(),seen=new Set();
  for(const d of m.decks){seen.add(d.id);let a=MONA.get(d.id);
   if(!a){a=new Audio();a.preload='auto';a._pos=d.pos;MONA.set(d.id,a);
    a.addEventListener('loadedmetadata',()=>{try{a.currentTime=a._pos+0.15}catch(e){}a.play().catch(()=>{})},{once:true});
    a.src='/api/library/file?id='+encodeURIComponent(d.fid)}
   a._pos=d.pos;a._gone=0;a._dv=d.vol;a.volume=Math.max(0,Math.min(1,d.vol*(+pvvol.value)));      // the preview volume applies to the soloed audio
   if(a.readyState>=1){if(a.paused)a.play().catch(()=>{});if(Math.abs(a.currentTime-d.pos)>0.4)a.currentTime=d.pos}}
  for(const [k,a] of MONA)if(!seen.has(k)){a.pause();if(!a._gone)a._gone=now;else if(now-a._gone>20000){a.removeAttribute('src');a.load();MONA.delete(k)}}
 }catch(e){}
 monT=setTimeout(monPoll,250)}
function soloLocal(on){bsolo=on;AU.muted=on;if(on)monPoll();else monStop()}
function toggleSolo(){
 const mode=pvt();
 if(mode==='pi'){cmd('solo');return}
 const want=!(mode==='browser'?bsolo:(bsolo||LASTSOLO));
 soloLocal(want);
 if(mode==='both')cmd('solo/'+(want?1:0));
 else soloUi({preview:{device:PVDEV}})}
/* ---- trim: In/Out points per track within a playlist ---- */
const tfmt=x=>{x=Math.max(0,x||0);const m=Math.floor(x/60),s=x-m*60;return m+':'+(s<9.95?'0':'')+s.toFixed(1)};
function tparse(v){v=String(v).trim().replace(',','.');if(!v)return null;let x=0;for(const q of v.split(':')){const n=parseFloat(q);if(!isFinite(n)||n<0)return NaN;x=x*60+n}return x}
const tmx=t=>{const m=t&&t.trim;return m&&(m.in||m.out!=null||m.start==='fade')?m:null};
const trimTxt=t=>('A '+(t.in?tfmt(t.in):'start')+(t.start==='fade'?' (fade in '+(((t.fade_in_ms||TRFADEIN)/1000).toFixed(1))+' s)':''))+', B '+(t.out!=null?tfmt(t.out):'end')+(t.out!=null&&t.end==='cut'?' (cut)':t.out!=null?' (fade'+(t.fade_ms?' '+(t.fade_ms/1000).toFixed(1)+' s':'')+')':'');
const tsh=x=>{x=Math.round(x*10)/10;const m=Math.floor(x/60),s=x-m*60;return m+':'+(s<10?'0':'')+(s%1?s.toFixed(1):s)};
function openTrimFocus(){const m=String(focid.textContent).match(/(\d+)\/(\d+)/);if(m&&PL[+m[1]]&&PL[+m[1]].tracks[+m[2]])openTrim(+m[1],+m[2])}
function updFocXf(){const x=cuePT();foc_xf.disabled=!x;if(document.activeElement===foc_xf)return;
 const v=x&&x.t.xfade!=null?String(x.t.xfade/1000):'';if(foc_xf.value!==v)foc_xf.value=v;foc_xf.placeholder=(window.tr_ms&&tr_ms.value)||'master';xfc.classList.toggle('on',!!v)}
async function focXfSave(){const x=cuePT();if(!x)return;const v=foc_xf.value.trim();
 const r=await fetch('/api/'+x.i+'/'+x.k+'/xftime/'+(v===''?'clear':encodeURIComponent(v)));const d=await r.json().catch(()=>({}));
 if(d.result&&d.result!=='ok')say('Crossfade time: 0 to 30 seconds.',false);lastHtml='';render(true)}
function updFocTrim(){const m=String(focid.textContent).match(/(\d+)\/(\d+)/),t=m&&PL[+m[1]]&&PL[+m[1]].tracks[+m[2]];
 const tm=tmx(t);foctrim.hidden=!tm;if(tm){foctrim.textContent=tm.in||tm.out!=null?'A–B '+(tm.in?tsh(tm.in):'0:00')+'–'+(tm.out!=null?tsh(tm.out):'end'):'Fade in';foctrim.title='This cued track is trimmed: '+trimTxt(tm)+'. Click to edit.'}
 foctrbtn.classList.toggle('on',!!tm);foctrbtn.disabled=!t}
/* trigger points: Live card, waveform flags and row badges */
let NT=null,LTR={fid:null,items:[]},TRGARM=true,LTN={seq:0,until:0,kind:'',txt:'',shown:''};
function trgApply(s){TRGARM=s.triggers_armed!==false;NT=s.next_trigger?{...s.next_trigger,t0:performance.now(),playing:LIVE.playing}:null;LTR=s.live_triggers||{fid:null,items:[]}}
function trgSync(s){trgApply(s);
 const n=s.trigger_notice;if(n&&n.seq!==LTN.seq){const k=n.kind;LTN={seq:n.seq,until:performance.now()+7000,kind:k,txt:(k==='fired'?'Trigger fired: ':k==='failed'?'Trigger failed: ':'Trigger skipped: ')+n.text,shown:''}}
 const any=PL.some(pl=>pl.tracks.some(t=>t.triggers&&t.triggers.length));
 trgarm.hidden=!(any||!TRGARM);trgarm.classList.toggle('off',!TRGARM);trgarm.classList.toggle('on',TRGARM);trgarm.setAttribute('aria-pressed',TRGARM);
 const h=icoSvg('flag',13)+(TRGARM?'Auto triggers on':'AUTO TRIGGERS OFF');if(trgarm._h!==h){trgarm._h=h;trgarm.innerHTML=h}
 trgarm.title=TRGARM?'Auto triggers are ON: trigger points play their track on top of the live track by themselves. Click to switch them off.':'Auto triggers are OFF: no trigger point will play. Click to switch them on.';
 trgTick()}
function trgTick(){if(!window.ltrg)return;const now=performance.now();
 const on=now<LTN.until;ltrn.hidden=!on;if(on&&LTN.shown!==LTN.txt){LTN.shown=LTN.txt;ltrn.textContent=LTN.txt;ltrn.className='ltrn '+LTN.kind}
 if(!NT){ltrg.hidden=true;return}
 const left=Math.max(0,NT.in_seconds-(NT.playing?(now-NT.t0)/1000:0)),soon=left<10&&!NT.next_pass;
 const t=`Next trigger in ${mmss(left)}${NT.next_pass?' (next pass)':''} → ${NT.target}${NT.missing?' (track missing: nothing will play)':''}${TRGARM?'':' (Auto triggers are off)'}`;
 ltrg.className='ltrg'+(NT.missing?' warn':!TRGARM?' offn':soon?' soon':'');ltrg.hidden=false;ltrg_skip.hidden=!TRGARM;
 if(ltrg._t!==t){ltrg._t=t;ltrg_txt.innerHTML=icoSvg('flag',14)+' '+esc(t)}}
async function trgArm(){const r=await fetch('/api/triggers/arm',{method:'POST',body:JSON.stringify({armed:!TRGARM})});const d=await r.json().catch(()=>({}));if(d.ok){trgApply(d);trgSync({...LASTS,...d})}}
async function trgSkip(){const r=await fetch('/api/triggers/skip',{method:'POST'});const d=await r.json().catch(()=>({}));
 if(d.ok){LTN={seq:LTN.seq,until:performance.now()+5000,kind:'skipped',txt:'Next trigger skipped: '+d.skipped.target+' will not play this time',shown:''};trgApply(d)}trgTick()}
function trgFlags(cv,dur){if(!dur||!LIVE.fid||LTR.fid!==LIVE.fid||!LTR.items.length)return;
 const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight,x=cv.getContext('2d'),c=cols();x.setTransform(dpr,0,0,dpr,0,0);
 for(const g of LTR.items){const xx=Math.min(W-1,g.at/dur*W),dead=g.fired||g.skipped||!TRGARM,bw=15,y=H-13,right=xx+bw+1<=W;
  x.globalAlpha=dead?.75:1;x.fillStyle=x.strokeStyle=dead?c.dim:c.trg;x.lineWidth=1.2;x.beginPath();x.moveTo(xx,y);x.lineTo(xx,H);x.stroke();
  x.beginPath();if(right){x.moveTo(xx,y);x.lineTo(xx+bw,y);x.lineTo(xx+bw-4,y+5);x.lineTo(xx+bw,y+10);x.lineTo(xx,y+10)}else{x.moveTo(xx,y);x.lineTo(xx-bw,y);x.lineTo(xx-bw+4,y+5);x.lineTo(xx-bw,y+10);x.lineTo(xx,y+10)}x.closePath();x.fill();
  x.fillStyle='#fff';x.font='bold 8px system-ui,sans-serif';x.textBaseline='middle';x.textAlign='center';x.fillText(String(g.n),right?xx+bw/2-1.5:xx-bw/2+1.5,y+5.5);x.textAlign='start'}
 x.globalAlpha=1}
function trgBadge(i,k,t){const L=t.triggers||[];if(!L.length)return '';const bad=L.some(g=>g.missing);
 const tip=L.length+' trigger point'+(L.length>1?'s':'')+': '+L.map(g=>tsh(g.at)+' → '+g.name+(g.enabled?'':' (off)')+(g.missing?' (missing)':'')).join('; ')+'. Click to edit.';
 return `<button class="trgbg${bad?' bad':''}" onclick="openTrim(${i},${k},'triggers')" title="${esc(tip)}" aria-label="${esc(tip)}">${icoSvg('flag',11)}${L.length}</button>`}
function trimBadge(i,k,t){const m=tmx(t);return m?`<span class=trb onclick="openTrim(${i},${k})" title="Trimmed: ${trimTxt(m)}${LIBDUR[t.id]?' (file is '+dtxt(LIBDUR[t.id])+' long)':''}. Click to edit.">${m.in||m.out!=null?(m.in?tsh(m.in):'0:00')+'–'+(m.out!=null?tsh(m.out):'end'):'Fade in'}</span>`:''}
function openTrim(p,k,sec){
 const t=PL[p].tracks[k],w=waveFor(t.id),full=(w&&w.dur)||LIBDUR[t.id]||0,tm=t.trim||{};
 tr_pp.innerHTML='';TR={p,k,fid:t.id,full,inn:tm.in||0,out:tm.out!=null?tm.out:full,end:tm.end||'fade',fade:tm.fade_ms||null,start:tm.start==='fade'?'fade':'cut',fadeIn:tm.fade_in_ms||null,loop:false,looping:false,cur:null,drag:null,aud:null,
  trg:(t.triggers||[]).map(g=>({id:g.id,at:g.at,file:g.file,once:!!g.once,enabled:g.enabled!==false,miss:!!g.missing,file0:g.file})),sel:null,testId:null};
 TR.trgOrig=trgSig();
 trname.textContent=trname2.textContent=PL[p].name+' › '+t.name;fillPvTarget();trmsg.textContent='';tr_clear.hidden=!tmx(t)&&!t.trim;tr_end.value=TR.end;trPrecUi();trLoopUi();trUpd();
 trg_add.innerHTML=icoSvg('flag',16)+'Add trigger at playhead';trpickClose();trgRender();
 trdlg.showModal();document.activeElement&&document.activeElement.blur();
 if(sec==='triggers')trgsec.scrollIntoView({block:'nearest'})}
/* trigger points: a local copy of the track's list that Save writes together with the trim, and Cancel throws away */
const TRGI={trash:'<svg width=16 height=16 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>'};
let TRG_LAST=null;const TR_TITLE=trwf.title;
const trgName=id=>id?id.replace(/\.[^.]+$/,'').split('/').pop():'Choose a track…';
const trgSig=()=>JSON.stringify(TR.trg.map(g=>[g.id||null,+(+g.at).toFixed(2),g.file,!!g.once,!!g.enabled]).sort((a,b)=>a[1]-b[1]));
function trgWarn(g){const w=[];
 if(!g.file)w.push('Choose the track to play');
 else if((g.miss&&g.file===g.file0)||(LIBF.length&&!LIBF.some(x=>x.id===g.file)))w.push('The target track is missing from the library: nothing will play');
 if(TR.full&&g.at>TR.full+.01)w.push('After the end of the file');
 else if(g.at<TR.inn-.001)w.push('Before point A: this trigger never fires');
 else if(g.at>=TR.out-.001)w.push('At or after point B: this trigger never fires');
 return w}
function trgSort(){TR.trg.sort((a,b)=>a.at-b.at)}
function trgSet(g,at){at=Math.round(Math.max(0,Math.min(at,TR.full||at))*100)/100;g.at=at}
function trgRender(){if(!TR)return;const L=TR.trg;trg_empty.hidden=L.length>0;
 trg_add.disabled=L.length>=16;
 trg_list.innerHTML=L.map((g,i)=>{const w=trgWarn(g);
  return `<div class="trgr${g.enabled?'':' off'}${TR.sel===g?' sel':''}" data-i=${i}>
  <span class=trgn title="Trigger ${i+1}">${icoSvg('flag',16)}${i+1}</span>
  <input class=tt data-f=at value="${tfmt(g.at)}" autocomplete=off aria-label="Trigger ${i+1} time (minutes:seconds)" title="Where in the file the trigger fires (mm:ss.s)">
  <button class="trgp${g.file?'':' none'}" data-f=file aria-haspopup=listbox title="${esc(g.file||'Choose the library track that plays on top')}">${esc(trgName(g.file))}</button>
  <span class=trgb><label class=fp title="Fire on the first pass only: a looping track will not fire it again"><input type=checkbox data-f=once ${g.once?'checked':''}>First pass only</label>
  <button class="trgen${g.enabled?' on':''}" data-f=en aria-pressed=${g.enabled} title="${g.enabled?'Enabled: click to switch this trigger off':'Switched off: click to enable'}">${g.enabled?'On':'Off'}</button>
  <button class=ib data-f=test title="Test: play the target track on the preview output" aria-label="Test trigger ${i+1}">${LI.play}</button>
  <button class=ib data-f=del title="Delete this trigger" aria-label="Delete trigger ${i+1}">${TRGI.trash}</button></span>
  ${w.length?`<div class=trgw>${w.map(x=>'⚠ '+esc(x)).join('')}</div>`:''}</div>`}).join('');
 if(TR.focusRow!=null){const el=trg_list.querySelector(`[data-i="${TR.focusRow}"] [data-f="${TR.focusF||'at'}"]`);TR.focusRow=null;el&&el.focus()}}
function trgAdd(){if(!TR||TR.trg.length>=16)return;
 let at=trPlayhead();if(at==null)at=TR.inn;
 const g={id:null,at:0,file:TRG_LAST&&LIBF.some(x=>x.id===TRG_LAST)?TRG_LAST:null,once:false,enabled:true};trgSet(g,at);
 TR.trg.push(g);trgSort();TR.sel=g;trmsg.textContent='';trgRender();
 const i=TR.trg.indexOf(g),row=trg_list.querySelector(`[data-i="${i}"]`);row&&row.scrollIntoView({block:'nearest'});
 if(!g.file){const b=row&&row.querySelector('[data-f=file]');b&&trgPick(i,b)}}
function trgDel(i){if(!TR||i<0)return;const g=TR.trg[i];TR.trg.splice(i,1);if(TR.sel===g)TR.sel=null;trpickClose();trgRender()}
function trgMove(sel,d){if(sel==='inn')TR.inn=Math.round(Math.max(0,Math.min(TR.inn+d,TR.out-.5))*100)/100;
 else if(sel==='out')TR.out=Math.round(Math.max(TR.inn+.5,Math.min(TR.out+d,TR.full||TR.out+d))*100)/100;
 else if(sel){trgSet(sel,sel.at+d);trgSort()}
 trUpd();trgRender()}
function trgTest(i){const g=TR.trg[i];if(!g||!g.file){trmsg.textContent='Choose the track to play first';return}
 trmsg.textContent='';trAudEnd(true);TR.testId=g.file;pvPlay({id:g.file})}
function trgSelect(sel){TR.sel=sel;trg_list.querySelectorAll('.trgr').forEach((r,i)=>r.classList.toggle('sel',TR.trg[i]===sel))}
trg_list.addEventListener('click',e=>{const b=e.target.closest('[data-f]');if(!b||!TR)return;const row=b.closest('.trgr'),i=+row.dataset.i,g=TR.trg[i],f=b.dataset.f;
 if(f==='file'){trgPick(i,b)}else if(f==='en'){g.enabled=!g.enabled;TR.focusRow=i;TR.focusF='en';trgRender()}
 else if(f==='test')trgTest(i);else if(f==='del')trgDel(i)});
trg_list.addEventListener('change',e=>{const b=e.target.closest('[data-f]');if(!b||!TR)return;const row=b.closest('.trgr'),g=TR.trg[+row.dataset.i];
 if(b.dataset.f==='once'){g.once=b.checked;return}
 if(b.dataset.f==='at'){const x=tparse(b.value);if(x==null||isNaN(x)){trmsg.textContent='Use minutes and seconds, like 1:23.5';b.value=tfmt(g.at);return}
  trmsg.textContent='';trgSet(g,x);trgSort();trgRender()}});
trg_list.addEventListener('focusin',e=>{const row=e.target.closest('.trgr');if(row&&TR&&TR.trg[+row.dataset.i]!==TR.sel)trgSelect(TR.trg[+row.dataset.i])});
/* the searchable target picker (the shared Cbo popover) */
let TRP=null;
function trgPick(i,btn){
 const items=LIBF.filter(x=>x.id===TR.trg[i].file||!isHid(upOf(x.id))).sort((a,b)=>a.id.toLowerCase().localeCompare(b.id.toLowerCase())).map(x=>{const j=x.id.lastIndexOf('/');return {v:x.id,t:trgName(x.id),sub:j>=0?x.id.slice(0,j):'',k:x.id}});
 TRP={i,btn};
 cboOpen({anchor:btn,items,current:TR.trg[i].file||'',max:300,empty:'No matching track in the library.',placeholder:'Search the library…',label:'Choose the track to play on top',
  onChoose:it=>{const g=TR.trg[i];g.file=it.v;TRG_LAST=g.file;TR.focusRow=i;TR.focusF='file';trmsg.textContent='';trgRender();trDraw()},
  onClose:()=>{TRP=null}})}
function trpickClose(){if(TRP)cboClose()}
trdlg.addEventListener('cancel',e=>{if(TRP){e.preventDefault();trpickClose()}});
function trUpd(){
 if(!TR)return;TR.inn=Math.max(0,Math.min(TR.inn,TR.out-.5));
 if(document.activeElement!==tr_in)tr_in.value=trTf(TR.inn);if(document.activeElement!==tr_out)tr_out.value=trTf(TR.out);
 const len=TR.out-TR.inn;tr_plays.textContent=TR.full?'Plays '+trT(len)+' of '+trT(TR.full):'';
 const fOn=TR.end==='fade'&&TR.out<TR.full-.01,eff=trFadeEff(),raw=TR.fade!=null?TR.fade:TRFADE;
 tr_fade.classList.toggle('dim',!fOn);tr_fv.disabled=!fOn;
 if(document.activeElement!==tr_fv)tr_fv.value=(eff/1000).toFixed(1);
 tr_fdef.hidden=TR.fade!=null||!fOn;tr_fuse.hidden=TR.fade==null||!fOn;
 const notes=[];
 if(fOn&&raw>eff+.5)notes.push('Fade out shortened to '+(eff/1000).toFixed(1)+' s: the fade cannot be longer than the part that plays (A to B).');
 tr_fadeinfo.textContent=fOn?'':TR.end==='cut'?'(stops dead at B)':'(only when B is set before the end)';
 const iOn=TR.start==='fade',ieff=trFadeInEff(),iraw=TR.fadeIn!=null?TR.fadeIn:TRFADEIN;
 tr_start.value=TR.start;tr_fadein.classList.toggle('dim',!iOn);tr_fiv.disabled=!iOn;
 if(document.activeElement!==tr_fiv)tr_fiv.value=(ieff/1000).toFixed(1);
 tr_fidef.hidden=TR.fadeIn!=null||!iOn;tr_fiuse.hidden=TR.fadeIn==null||!iOn;
 tr_fiinfo.textContent=iOn?'':'(starts at full level)';
 if(iOn&&iraw>ieff+.5)notes.push('Fade in shortened to '+(ieff/1000).toFixed(1)+' s: the fade cannot be longer than the part that plays (A to B).');
 tr_fnote.textContent=notes.join(' ');
 document.querySelectorAll('#trgrid .stp').forEach(b=>{b.disabled=b.dataset.fd==='in'?!iOn:!fOn})}
/* Precision (time fields with arrows and the step strip) and the fade-in at A */
let TRPREC=true,TRSTEP=.1;try{TRPREC=localStorage.getItem('cp_trprec')!=='0';const st=+localStorage.getItem('cp_trstep');if([.01,.1,1].includes(st))TRSTEP=st}catch(e){}
document.querySelectorAll('#trgrid .trprec').forEach(b=>b.innerHTML=icoSvg('sliders-horizontal',16));
function trPrecUi(){trgrid.classList.toggle('noprec',!TRPREC);
 document.querySelectorAll('#trgrid .trprec').forEach(b=>{b.classList.toggle('on',TRPREC);b.setAttribute('aria-pressed',TRPREC)});
 document.querySelectorAll('#trgrid .trseg button').forEach(b=>{const on=+b.dataset.s===TRSTEP;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on)})}
function trPrec(){TRPREC=!TRPREC;try{localStorage.setItem('cp_trprec',TRPREC?'1':'0')}catch(e){}trPrecUi()}
function trTf(x){if(TRSTEP>=.1||!isFinite(x))return trT(x);x=Math.round(Math.max(0,x)*100)/100;const h=Math.floor(x/3600),r=x-h*3600,m=Math.floor(r/60),sc=r-m*60,ss=(sc<9.995?'0':'')+sc.toFixed(2);return h?h+':'+String(m).padStart(2,'0')+':'+ss:m+':'+ss}
function trNudge(f,d,big){if(!TR)return;const v=Math.round(((f==='inn'?TR.inn:TR.out)+d*TRSTEP*(big?10:1))*100)/100;
 if(f==='inn')TR.inn=Math.max(0,Math.min(v,TR.out-.5));else TR.out=Math.max(TR.inn+.5,Math.min(v,TR.full||v));
 trmsg.textContent='';trUpd()}
let trNT1=0,trNT2=0;const trNudgeStop=()=>{clearTimeout(trNT1);clearInterval(trNT2)};
trgrid.addEventListener('pointerdown',e=>{const b=e.target.closest('.tma button');if(!b||!TR)return;e.preventDefault();trNudgeStop();const f=b.dataset.f,d=+b.dataset.d,big=e.shiftKey;
 trNudge(f,d,big);trNT1=setTimeout(()=>{trNT2=setInterval(()=>trNudge(f,d,big),80)},420)});
for(const ev of ['pointerup','pointercancel','pointerleave'])trgrid.addEventListener(ev,trNudgeStop);
function trFadeStep(w,d){if(!TR)return;if(w==='in')trFadeInSet(trFadeInEff()/1000+d*.1);else trFadeSet(trFadeEff()/1000+d*.1)}
trgrid.addEventListener('pointerdown',e=>{const b=e.target.closest('.stp');if(!b||!TR||b.disabled)return;e.preventDefault();trNudgeStop();const w=b.dataset.fd,d=+b.dataset.d;
 trFadeStep(w,d);trNT1=setTimeout(()=>{trNT2=setInterval(()=>trFadeStep(w,d),110)},420)});
trgrid.addEventListener('keydown',e=>{const i=e.target.closest('#tr_in,#tr_out');if(!i||(e.key!=='ArrowUp'&&e.key!=='ArrowDown'))return;e.preventDefault();trNudge(i.id==='tr_in'?'inn':'out',e.key==='ArrowUp'?1:-1,e.shiftKey)});
trgrid.addEventListener('click',e=>{const b=e.target.closest('.trseg button');if(!b)return;TRSTEP=+b.dataset.s;try{localStorage.setItem('cp_trstep',String(TRSTEP))}catch(x){}trPrecUi();if(TR)trUpd()});
/* the fade in at A: TR.start = 'cut' (the default) or 'fade'; TR.fadeIn = this track's own length in ms, or null = the default (TRFADEIN); the value is kept while the edge is Cut */
const trFadeInWin=()=>Math.max(100,Math.round((TR.out-TR.inn)*1000));
function trFadeInEff(){const raw=TR.fadeIn!=null?TR.fadeIn:TRFADEIN;return raw<=0?0:Math.max(100,Math.min(raw,trFadeInWin(),10000))}
function trStart(v){TR.start=v==='fade'?'fade':'cut';if(TR.start==='fade'&&trFadeInEff()===0)TR.fadeIn=1500;trUpd()}
function trFadeInSet(v){const x=parseFloat(String(v).replace(',','.'));
 if(isNaN(x)){trmsg.textContent='Use a number of seconds, like 1.5';trUpd();tr_fiv.value=(trFadeInEff()/1000).toFixed(1);return}
 trmsg.textContent='';TR.fadeIn=Math.max(100,Math.min(10000,Math.round(x*10)*100));trUpd();tr_fiv.value=(trFadeInEff()/1000).toFixed(1)}
function trFadeInDef(){TR.fadeIn=null;trUpd()}
/* the fade at B: TR.fade = this track's own length in ms, or null = the default (TRFADE); never longer than the played part */
const trFadeWin=()=>Math.max(100,Math.round((TR.out-TR.inn)*1000));
function trFadeEff(){const raw=TR.fade!=null?TR.fade:TRFADE;return Math.max(100,Math.min(raw,trFadeWin(),10000))}
function trFadeSet(v){const x=parseFloat(String(v).replace(',','.'));   /* no blur: the spinner arrows and Up/Down keys fire 'change' on every step and must keep the focus */
 if(isNaN(x)){trmsg.textContent='Use a number of seconds, like 1.5';trUpd();tr_fv.value=(trFadeEff()/1000).toFixed(1);return}
 trmsg.textContent='';TR.fade=Math.max(100,Math.min(10000,Math.round(x*10)*100));trUpd();tr_fv.value=(trFadeEff()/1000).toFixed(1)}
function trFadeDef(){TR.fade=null;trUpd()}
function trField(f,v){if(document.activeElement)document.activeElement.blur();const x=tparse(v);if(x==null||isNaN(x)){trmsg.textContent='Use minutes and seconds, like 1:23.5';trUpd();return}
 trmsg.textContent='';if(TR.full)TR[f]=Math.min(x,TR.full);else TR[f]=x;if(f==='inn')TR.inn=Math.min(TR.inn,TR.out-.5);else TR.out=Math.max(TR.out,TR.inn+.5);trUpd()}
function trHere(f){const x=trPlayhead();if(x==null){trmsg.textContent='Preview the track or click the waveform to choose a position first';return}
 trmsg.textContent='';if(f==='inn')TR.inn=Math.min(x,TR.out-.5);else TR.out=Math.max(x,TR.inn+.5);trUpd()}
function trPlayhead(){if(PVCUR.id===TR.fid&&PVCUR.state!=='stopped')return pvPosDur()[0];return TR.cur}
/* time bubble over the trim waveform: DOM overlay (no canvas redraw); hh:mm:ss.s past an hour */
const trT=x=>{x=Math.round(Math.max(0,x||0)*10)/10;if(x<3600)return tfmt(x);const h=Math.floor(x/3600),r=x-h*3600,m=Math.floor(r/60),s=r-m*60;return h+':'+String(m).padStart(2,'0')+':'+(s<9.95?'0':'')+s.toFixed(1)};
function trPh(){const ph=TR&&trPlayhead(),s=ph==null||ph===false?'':'Playhead '+trT(ph);if(tr_ph._s!==s){tr_ph._s=s;tr_ph.textContent=s}}
function trTipHide(){trtip.hidden=true;trcur.hidden=true}
function trTip(e,t){
 if(!TR||!TR.full){trTipHide();return}
 const r=trwf.getBoundingClientRect(),d=trdlg.getBoundingClientRect(),touch=e.pointerType==='touch';
 t=Math.max(0,Math.min(TR.full,t));const x=r.left+t/TR.full*r.width;
 const a=trT(t),b='\u2212'+trT(TR.full-t);
 if(trtip_a._s!==a){trtip_a._s=a;trtip_a.textContent=a}if(trtip_b._s!==b){trtip_b._s=b;trtip_b.textContent=b}
 trcur.hidden=false;trcur.style.left=(x-.5)+'px';trcur.style.top=r.top+'px';trcur.style.height=r.height+'px';
 trtip.hidden=false;const bw=trtip.offsetWidth,bh=trtip.offsetHeight,minL=d.left+6,maxL=Math.max(minL,d.right-6-bw);
 let L=x-bw/2;if(L<minL)L=x+8;else if(L>maxL)L=x-8-bw;L=Math.max(minL,Math.min(L,maxL));
 let T=r.top-bh-6;if(T<Math.max(4,d.top+4))T=r.top+4;
 const m=touch?28:8;if(e.clientX>=L-m&&e.clientX<=L+bw+m&&e.clientY>=T-m&&e.clientY<=T+bh+m)T=r.bottom+6;   /* never under the pointer or finger */
 trtip.style.left=L+'px';trtip.style.top=Math.max(4,T)+'px'}
function trTipFor(e,t){const dr=TR.drag;trTip(e,dr==='inn'?TR.inn:dr==='out'?TR.out:dr==='trg'&&TR.dg?TR.dg.at:t)}
const trPhone=()=>matchMedia('(max-width:34rem)').matches;
function trDraw(){
 trPh();
 const cv=trwf,w=waveFor(TR.fid);if(w&&w.dur&&!TR.full){TR.full=w.dur;if(!TR.out||TR.out<=0)TR.out=w.dur;trUpd()}
 const full=TR.full||(w&&w.dur)||0,c=cols(),ph=trPlayhead();
 drawWave(cv,w,-1,c.pv,wmsg(w,''),null);
 const dpr=window.devicePixelRatio||1,W=cv.clientWidth,H=cv.clientHeight;if(!W||!full||!w||!w.peaks.length)return;
 const x=cv.getContext('2d'),X=t=>t/full*W;x.setTransform(dpr,0,0,dpr,0,0);
 x.globalAlpha=.55;x.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--panel2').trim()||'#222';
 x.fillRect(0,0,X(TR.inn),H);x.fillRect(X(TR.out),0,W-X(TR.out),H);x.globalAlpha=1;
 for(const [t,col,l] of [[TR.inn,'#2fa84f','A'],[TR.out,'#e5484d','B']]){
  x.fillStyle=col;x.fillRect(Math.min(W-3,Math.max(0,X(t)-1.5)),0,3,H);
  if(trPhone()){const gx=Math.min(W-12,Math.max(12,X(t)));x.beginPath();x.arc(gx,H-17,11,0,7);x.fillStyle=col;x.fill();x.lineWidth=2;x.strokeStyle='#fff';x.stroke();x.fillStyle=col}
  const fx=l==='A'?X(t):X(t)-30;x.fillRect(Math.max(0,Math.min(W-30,fx)),0,30,16);x.fillStyle='#fff';x.font='bold 11px system-ui,sans-serif';x.textBaseline='middle';x.fillText(l,Math.max(0,Math.min(W-30,fx))+7,8)}
 TR.wedgeA=null;
 if(TR.start==='fade'&&trFadeInEff()>0){const fl=trFadeInEff()/1000,xi=X(TR.inn),xe=Math.max(xi+8,Math.min(X(TR.inn+fl),X(TR.out)-8));
  x.globalAlpha=.28;x.fillStyle='#2fa84f';x.beginPath();x.moveTo(xi,0);x.lineTo(xe,0);x.lineTo(xe,H*.12);x.lineTo(xi,H-4);x.closePath();x.fill();
  x.globalAlpha=.9;x.strokeStyle='#2fa84f';x.lineWidth=1.5;x.beginPath();x.moveTo(xi,H-4);x.lineTo(xe,H*.12);x.stroke();
  if(xe-xi>40){x.fillStyle='#fff';x.font='bold 10px system-ui,sans-serif';x.textBaseline='middle';x.textAlign='left';x.fillText(fl.toFixed(1)+' s',xi+6,H*.5);x.textAlign='start'}x.globalAlpha=1;TR.wedgeA=[xi,xe]}
 if(TR.end==='fade'&&TR.out<full-.01){const fl=trFadeEff()/1000,xo=X(TR.out),xi=X(TR.inn),fx=Math.max(xi,Math.min(X(Math.max(TR.inn,TR.out-fl)),xo-8));   /* at least 8 px wide, even on a long track */
  x.globalAlpha=.28;x.fillStyle='#e5484d';x.beginPath();x.moveTo(fx,0);x.lineTo(xo,0);x.lineTo(xo,H-4);x.lineTo(fx,H*.12);x.closePath();x.fill();
  x.globalAlpha=.9;x.strokeStyle='#e5484d';x.lineWidth=1.5;x.beginPath();x.moveTo(fx,H*.12);x.lineTo(xo,H-4);x.stroke();
  if(xo-fx>40){x.fillStyle='#fff';x.font='bold 10px system-ui,sans-serif';x.textBaseline='middle';x.textAlign='right';x.fillText(fl.toFixed(1)+' s',xo-6,H*.5);x.textAlign='start'}x.globalAlpha=1;TR.wedge=[fx,xo]}else TR.wedge=null
 TR.trg.forEach((g,i)=>{const xx=X(Math.min(g.at,full)),sel=TR.sel===g,bad=trgWarn(g).length>0,bw=24,y=H-20,right=xx+bw+2<=W,fx=right?xx:xx-bw;
  x.globalAlpha=g.enabled?1:.45;x.strokeStyle=c.trg;x.fillStyle=c.trg;x.lineWidth=sel?3:1.5;x.setLineDash(g.enabled?[]:[4,3]);
  x.beginPath();x.moveTo(xx,0);x.lineTo(xx,H);x.stroke();x.setLineDash([]);
  x.beginPath();if(right){x.moveTo(xx,y);x.lineTo(xx+bw,y);x.lineTo(xx+bw-6,y+8);x.lineTo(xx+bw,y+16);x.lineTo(xx,y+16)}
  else{x.moveTo(xx,y);x.lineTo(xx-bw,y);x.lineTo(xx-bw+6,y+8);x.lineTo(xx-bw,y+16);x.lineTo(xx,y+16)}x.closePath();x.fill();
  if(sel){x.strokeStyle='#fff';x.lineWidth=1.5;x.stroke()}
  x.fillStyle='#fff';x.font='bold 11px system-ui,sans-serif';x.textBaseline='middle';x.textAlign='center';x.fillText(String(i+1),fx+bw/2-(right?2:-2),y+8.5);x.textAlign='start';
  if(bad){x.fillStyle='#e5484d';x.beginPath();x.arc(xx,8,5,0,7);x.fill();x.fillStyle='#fff';x.font='bold 9px system-ui,sans-serif';x.textAlign='center';x.fillText('!',xx,8.5);x.textAlign='start'}
  x.globalAlpha=1});
 if(ph!=null){x.fillStyle=c.text;x.fillRect(Math.min(W-2,Math.max(0,X(ph)-1)),0,2,H)}}
(function(){const cv=document.getElementById('trwf');
 const tt=e=>{const r=cv.getBoundingClientRect();return Math.max(0,Math.min(1,(e.clientX-r.left)/r.width))*(TR.full||0)};
 cv.addEventListener('pointerdown',e=>{if(!TR||!TR.full)return;const t=tt(e),r=cv.getBoundingClientRect(),px=TR.full?r.width/TR.full:1;
  const dI=Math.abs(t-TR.inn)*px,dO=Math.abs(t-TR.out)*px,tol=trPhone()?24:12;
  let gi=-1,gd=1e9;TR.trg.forEach((g,n)=>{const d=Math.abs(t-g.at)*px;if(d<gd){gd=d;gi=n}});
  const low=e.clientY-r.top>r.height-24;                         /* the flags sit along the bottom edge: they win there */
  const tg=gi>=0&&(low?gd<=26:gd<=12)&&(gd<=Math.min(dI,dO)||low);
  TR.drag=tg?'trg':Math.min(dI,dO)<=tol?(dI<=dO?'inn':'out'):'cur';TR.moved=false;TR.dg=tg?TR.trg[gi]:null;try{cv.setPointerCapture(e.pointerId)}catch(_){}cv.focus({preventScroll:true});e.preventDefault();
  if(TR.drag==='cur'){TR.sel=null;trgSelect(null);trCur(t)}else{trgSelect(TR.drag==='trg'?TR.dg:TR.drag);if(TR.drag==='trg'){const row=trg_list.querySelector(`[data-i="${TR.trg.indexOf(TR.dg)}"]`);row&&row.scrollIntoView({block:'nearest'})}}
  trTipFor(e,t)});
 cv.addEventListener('pointermove',e=>{if(!TR||!TR.full)return;const t=tt(e);
  if(!TR.drag){const r=cv.getBoundingClientRect(),px=r.width/TR.full;cv.style.cursor=Math.min(Math.abs(t-TR.inn),Math.abs(t-TR.out),...TR.trg.map(g=>Math.abs(t-g.at)))*px<=12?'ew-resize':'crosshair';trTip(e,t);{const wx=e.clientX-r.left,w=TR.wedge,wa=TR.wedgeA,nt=w&&wx>=w[0]-2&&wx<=w[1]+2?'Fade out at B: '+(trFadeEff()/1000).toFixed(1)+' s'+(TR.fade==null?' (default)':''):wa&&wx>=wa[0]-2&&wx<=wa[1]+2?'Fade in at A: '+(trFadeInEff()/1000).toFixed(1)+' s'+(TR.fadeIn==null?' (default)':''):TR_TITLE;if(cv.title!==nt)cv.title=nt}return}
  TR.moved=true;if(TR.drag==='inn')TR.inn=Math.min(t,TR.out-.5);else if(TR.drag==='out')TR.out=Math.max(t,TR.inn+.5);else if(TR.drag==='trg'){trgSet(TR.dg,t);trgRender()}else trCur(t);trUpd();trTipFor(e,t)});
 const up=e=>{if(!TR)return;if(TR.drag==='trg'){trgSort();trgRender()}TR.drag=null;TR.dg=null;if(e&&e.pointerType==='touch')trTipHide()};
 cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',e=>{up(e);trTipHide()});
 cv.addEventListener('pointerleave',()=>{if(!TR||!TR.drag)trTipHide()});
 cv.addEventListener('keydown',e=>{if(!TR)return;
  const order=()=>['inn',...TR.trg,'out'].sort((a,b)=>(typeof a==='string'?(a==='inn'?TR.inn:TR.out):a.at)-(typeof b==='string'?(b==='inn'?TR.inn:TR.out):b.at));
  if(e.key==='ArrowUp'||e.key==='ArrowDown'){const o=order(),n=o.indexOf(TR.sel),m=n<0?(e.key==='ArrowDown'?0:o.length-1):(n+(e.key==='ArrowDown'?1:-1)+o.length)%o.length;trgSelect(o[m]);e.preventDefault();return}
  if((e.key==='Delete'||e.key==='Backspace')&&TR.sel&&typeof TR.sel==='object'){trgDel(TR.trg.indexOf(TR.sel));e.preventDefault();return}
  const step=e.shiftKey?1:e.altKey?.01:.1,d=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0;
  if(d&&TR.sel){e.preventDefault();trgMove(TR.sel,d)}})})();
function trCur(t){TR.cur=t;if(PVCUR.id===TR.fid&&['playing','paused'].includes(PVCUR.state)){PVST.pos=t;PVST.t0=performance.now();pvCtl('seek',{pos:t})}}
/* audition through the normal preview, so it can be heard on the browser, the preview output or both */
function trAudEnd(restore){const a=TR&&TR.aud;if(!a)return;clearInterval(a.t);TR.aud=null;TR.looping=false;trLoopUi();if(restore)pvCtl('vol',{v:a.vol0})}
async function trPP(){
 const same=PVCUR.id===TR.fid;
 if(same&&PVCUR.state==='playing'){await pvCtl('pause')}
 else if(same&&PVCUR.state==='paused'){await pvCtl('resume')}
 else trAud(TR.cur!=null?TR.cur:TR.inn,TR.full||TR.out,true)}
async function trStop(){const x=trPlayhead();trAudEnd(true);if(PVCUR.id===TR.fid&&PVCUR.state!=='stopped'){await pvCtl('stop');if(x!=null)TR.cur=x}}
function trIcons(){if(!tr_x.innerHTML)tr_x.innerHTML='<svg width=18 height=18 viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round aria-hidden=true><path d="M6 6l12 12M18 6 6 18"/></svg>';const pl=PVCUR.id===TR.fid&&PVCUR.state==='playing';if(tr_pp._p!==pl||!tr_pp.innerHTML){tr_pp._p=pl;tr_pp.innerHTML=pl?LI.pause:LI.play}if(!tr_stop.innerHTML)tr_stop.innerHTML=LI.stop;
 if(!tr_ab.innerHTML)tr_ab.innerHTML=LI.play+'<b>A-B</b>';if(!tr_loop.innerHTML)tr_loop.innerHTML=IC.loop+'<b>A-B</b>'}
/* Loop A-B is preview only. On the player's preview output the worker loops [A, B) itself (one buffer, sample-accurate, both fades every lap); on This browser (and Both) the page seeks back
   to A at B, which leaves a small gap. It never touches the live decks. Per dialog open, not saved. */
function trLoopUi(){if(!TR)return;tr_loop.classList.toggle('on',!!TR.loop);tr_loop.setAttribute('aria-pressed',!!TR.loop);tr_loopnote.hidden=!TR.loop;
 tr_loopnote.textContent=TR.loop?'Loop on: Play A-B repeats from A each time it reaches B, fades applied. Stop or switch Loop off to end it.'+(pvt()==='pi'?'':' On This browser the wrap has a small gap; the player\u2019s preview output loops without one.'):''}
function trLoopTog(){if(!TR)return;TR.loop=!TR.loop;trLoopUi();
 if(TR.loop){if(TR.aud&&!TR.aud.whole)trAud(TR.inn,TR.out,false,true)}
 else if(TR.looping)trStop()}
const trFadeInMs=from=>TR.start==='fade'&&Math.abs(from-TR.inn)<.05?trFadeInEff():0;
const trFadeOutMs=to=>TR.end==='fade'&&TR.out<TR.full-.01&&Math.abs(to-TR.out)<.05?trFadeEff():0;
async function trAud(from,to,whole,loop){
 trAudEnd(true);trmsg.textContent='';
 const act=PVCUR.id===TR.fid&&['playing','loading','paused'].includes(PVCUR.state);
 if(!act)await pvPlay({id:TR.fid});
 const ready=()=>['playing','paused'].includes(PVCUR.state)&&(pvt()==='browser'?isFinite(AU.duration)&&AU.readyState>=1:PVST.dur>0);
 for(let n=0;n<80;n++){if(!TR)return;if(ready())break;await new Promise(r=>setTimeout(r,100))}
 if(!TR||!ready()){trmsg.textContent='The preview could not start (is a preview output set, or is the browser blocking sound?)';return}
 const vol0=+pvvol.value||1,fin=whole?0:trFadeInMs(from),fout=whole?0:trFadeOutMs(to),lp=!!(loop&&!whole);
 if(lp&&pvt()==='pi'){                                   // the worker loops it, with both fades, without a gap
  const r=await fetch('/api/preview/ctl',{method:'POST',body:JSON.stringify({cmd:'loop',a:from,b:to,fin,fout})});
  if(!r.ok){trmsg.textContent='The loop could not start';return}
  pvPoll();TR.looping=true;TR.aud={vol0,whole:false,t:setInterval(()=>{if(!TR||PVCUR.state==='stopped')trAudEnd(true)},200)};trLoopUi();return}
 if(fin>0)await pvCtl('vol',{v:0});                       // the fade-in starts from silence
 await pvCtl('seek',{pos:from});if(PVCUR.state==='paused')await pvCtl('resume');
 let lastV=0,lap0=performance.now(),cur=fin>0?0:vol0;
 const setV=(v,now)=>{if(now-lastV>90&&Math.abs(v-cur)>.01||(v===vol0&&cur!==vol0)){lastV=now;cur=v;pvCtl('vol',{v})}};
 TR.looping=lp;TR.aud={vol0,whole:!!whole,t:setInterval(()=>{
  const pp=pvPosDur()[0],now=performance.now();
  if(!whole&&pp>=to-.03){
   if(lp){pvCtl('seek',{pos:from});lap0=now;if(fin>0){cur=0;pvCtl('vol',{v:0})}else if(cur!==vol0){cur=vol0;pvCtl('vol',{v:vol0})}return}
   trAudEnd(true);pvCtl('pause');return}
  if(!whole){const f=fout/1000,left=to-pp;
   if(fin>0&&now-lap0<fin)setV(vol0*Math.sin((now-lap0)/fin*Math.PI/2),now);
   else if(fout>0&&left<f)setV(Math.max(0,vol0*Math.cos((1-left/f)*Math.PI/2)),now);
   else setV(vol0,now)}
  if(PVCUR.state==='stopped')trAudEnd(true)},60)};trLoopUi()}
async function trSave(){
 const badT=TR.trg.findIndex(g=>!g.file||(TR.full&&g.at>TR.full+.01));
 if(badT>=0){const g=TR.trg[badT];trmsg.textContent=`Trigger ${badT+1}: ${g.file?'its time is after the end of the file':'choose the track to play'}`;trgSelect(g);return}
 const body={track:TR.k,in:TR.inn>.01?+TR.inn.toFixed(2):null,out:TR.full&&TR.out<TR.full-.01?+TR.out.toFixed(2):null,end:TR.end,fade_ms:TR.fade!=null?trFadeEff():null,start:TR.start==='fade'?'fade':null,fade_in_ms:TR.fadeIn!=null?trFadeInEff():null};
 const r=await fetch(`/api/playlists/${TR.p}/trim`,{method:'POST',body:JSON.stringify(body)});
 if(!r.ok){let m='Could not save';try{m=(await r.json()).error||m}catch(e){}trmsg.textContent=m;return}
 if(trgSig()!==TR.trgOrig){
  const r2=await fetch(`/api/playlists/${TR.p}/triggers`,{method:'POST',body:JSON.stringify({track:TR.k,action:'set',triggers:TR.trg.map(g=>({id:g.id||undefined,at:+(+g.at).toFixed(2),file:g.file,once:!!g.once,enabled:!!g.enabled}))})});
  if(!r2.ok){let m='Could not save the trigger points';try{m=(await r2.json()).error||m}catch(e){}trmsg.textContent=m;return}}
 trdlg.close();lastHtml='';render(true)}
async function trClear(){await fetch(`/api/playlists/${TR.p}/trim`,{method:'POST',body:JSON.stringify({track:TR.k,clear:true})});trdlg.close();lastHtml='';render(true)}
trdlg.addEventListener('close',()=>{trTipHide();trwf.title=TR_TITLE;trpickClose();if(TR){trNudgeStop();const lp=TR.looping;trAudEnd(true);if(lp&&PVCUR.id===TR.fid)pvCtl('stop');else if(PVCUR.id===TR.fid&&PVCUR.state==='playing')pvCtl('pause');if(TR.testId&&PVCUR.id===TR.testId&&PVCUR.state!=='stopped')pvCtl('stop')}TR=null});
/* download from a link */
let dlT=null;
let DLD={state:'idle',ids:[]};
function dlGoto(){const f=(DLD.ids||[])[0];dldlg.close();dlChipHide();if(f)flashFolder(f)}
function dlChipHide(){dlchip.hidden=true}
function dlChip(d){
 if(dldlg.open||d.state==='idle'){dlchip.hidden=true;return}
 const n=(d.ids||[]).length;
 dlchip.className=d.state;dlchip.hidden=false;
 dlchipt.textContent=d.state==='running'?'Downloading '+Math.round(d.pct||0)+'%'+(d.title?': '+d.title:''):d.state==='done'?'Saved '+(n===1?'1 track':n+' tracks')+'. Click to show it in the library':'Download failed. Click for details';
 dlchipx.hidden=d.state==='running'}
async function dlChipClick(){
 if(DLD.state==='done'&&(DLD.ids||[]).length){const f=DLD.ids[0];dlchip.hidden=true;try{await fetch('/api/download/clear',{method:'POST'})}catch(e){}dlShow({state:'idle'});flashFolder(f);return}
 openDl()}
async function dlChipClose(e){e.stopPropagation();dlchip.hidden=true;try{await fetch('/api/download/clear',{method:'POST'})}catch(x){}dlShow({state:'idle'})}
function dlShow(d){
 DLD=d;dl_close.textContent=d.state==='running'?'Minimise':'Close';dl_show.hidden=!(d.state==='done'&&(d.ids||[]).length);dlChip(d);
 const run=d.state==='running';
 dl_prog.hidden=d.state==='idle';dl_bar.style.width=(d.pct||0)+'%';
 dl_msg.className='msg'+(d.state==='error'?' bad':d.state==='done'?' ok':'');
 dl_msg.textContent=(run&&d.title?d.title+': ':'')+(d.msg||'')+(run?' '+Math.round(d.pct||0)+'%':'')+(d.note?' '+d.note:'');
 dl_go.disabled=run;dl_go.textContent=run?'Downloading...':'Download';
 dlbtn.classList.toggle('busy',run);dlbtn.title=run?'Downloading: '+Math.round(d.pct||0)+'%':'Download audio from a link. It is saved in the Downloads folder of the library.'}
async function dlPoll(){
 clearTimeout(dlT);
 try{const d=await j('/api/download');dlShow(d);
  if(d.state==='running')dlT=setTimeout(dlPoll,1000);
  else if(d.state==='done'){lastLib='';render(true)}}catch(e){dlT=setTimeout(dlPoll,3000)}}
function openDl(){try{dl_fmt.value=localStorage.getItem('cp_dlfmt')||dl_fmt.value}catch(e){}dldlg.showModal();dl_url.focus();dlPoll()}
async function dlStart(){
 const url=dl_url.value.trim();if(!url){dl_url.focus();return}
 try{localStorage.setItem('cp_dlfmt',dl_fmt.value)}catch(e){}
 const r=await fetch('/api/download',{method:'POST',body:JSON.stringify({url,format:dl_fmt.value,playlist:dl_pl.checked})});
 const e=await r.json().catch(()=>({}));
 if(!r.ok){dlShow({state:'error',msg:e.error||'Could not start the download.',pct:0});return}
 dlPoll()}
dl_url.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();dlStart()}});
dldlg.addEventListener('close',async()=>{try{const d=await j('/api/download');if(d.state!=='running'){await fetch('/api/download/clear',{method:'POST'});dlShow({state:'idle'});dl_url.value=''}else dlPoll()}catch(e){}});
dlPoll();

/* custom layout: per browser (localStorage), wide screens only. The five blocks keep their elements and ids, they are only moved.
   Free-form grid: 12 columns, rows of GU px with a GG px gap. Every block is {x,y,w,h} in grid cells. Blocks snap to the grid, never overlap
   (a block that is in the way is pushed down) and float up to close vertical gaps. A block that is taller than its box scrolls inside it. */
const LB={cl:{n:'Live',h:7},fs:{n:'Cue',h:5},pv:{n:'Preview',h:6},inpc:{n:'Live input',h:5},libcol:{n:'Library',h:20},plcol:{n:'Playlists',h:20}};
const DW={cl:4,fs:2,pv:2,inpc:4,libcol:2,plcol:2},LKEY='cp_layout',LEL={};
const GC=12,GU=24,GG=8,GMINW=3,GMINH=3,GMAXH=80;
for(const id of Object.keys(LB))LEL[id]=document.getElementById(id);
const LHOME={now:document.getElementById('now'),cuerow:document.getElementById('cuerow'),cols:document.getElementById('cols')};
let LAY=null,LPOS=null,LEDIT=false,LOP=null,layT=null,LAYWAS=null,LAY0='';
const LSZ=[[3,'¼','Quarter width'],[6,'½','Half width'],[9,'¾','Three-quarter width'],[12,'1','Full width']];
const lov=(a,b)=>a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h;
/* collision rule: the fixed block (the one being moved or resized) keeps its place; every other block, in reading order, takes the highest free spot at or below the top */
function layPack(list,fixed){
 const order=[...list].sort((a,b)=>(a.id===fixed?-1:b.id===fixed?1:0)||a.y-b.y||a.x-b.x),placed=[];
 for(const b of order){const c={...b};if(c.id!==fixed)c.y=0;while(placed.some(p=>lov(p,c)))c.y++;placed.push(c)}
 return placed}
const layItems=(L,all)=>Object.keys(LB).filter(id=>all||!L.hide.includes(id)).map(id=>({id,...L.b[id]}));
const layMap=list=>Object.fromEntries(list.map(p=>[p.id,{x:p.x,y:p.y,w:p.w,h:p.h}]));
function layFromRows(rows,w){
 const b={};let y=0;
 for(const r of rows){let x=0,rh=0;for(const id of r){b[id]={x:x*3,y,w:w[id]*3,h:LB[id].h};x+=w[id];rh=Math.max(rh,LB[id].h)}y+=rh}
 return b}
/* repair step: accepts anything that was ever saved (v1 and v2 rows, v3 grid, damaged data) and returns a valid grid layout, or null */
function layNorm(o){
 if(!o||typeof o!=='object')return null;
 const hide=Array.isArray(o.hide)?o.hide.filter(id=>LB[id]):[];let b={};
 if(o.b&&typeof o.b==='object'){for(const id of Object.keys(LB)){const q=o.b[id];if(q&&typeof q==='object')b[id]={x:+q.x,y:+q.y,w:+q.w,h:+q.h}}}
 else if(Array.isArray(o.rows)){
  const seen=new Set(),rows=[];
  for(const r of o.rows){if(!Array.isArray(r))continue;const row=r.filter(id=>LB[id]&&!seen.has(id)&&seen.add(id));if(row.length)rows.push(row)}
  const w={};for(const id of Object.keys(LB)){const v=o.w&&+o.w[id];w[id]=v>=1&&v<=4?Math.round(v):DW[id]}
  if(!o.w)for(const r of rows)if(r.length===1)w[r[0]]=4;
  const fr=[];for(const r of rows){let cur=[],t=0;for(const id of r){if(t+w[id]>4&&cur.length){fr.push(cur);cur=[];t=0}cur.push(id);t+=w[id]}if(cur.length)fr.push(cur)}
  b=layFromRows(fr,w)}
 else return null;
 const list=[];
 for(const id of Object.keys(LB)){const q=b[id];if(!q||![q.x,q.y,q.w,q.h].every(Number.isFinite))continue;
  const w=Math.min(GC,Math.max(GMINW,Math.round(q.w))),h=Math.min(GMAXH,Math.max(GMINH,Math.round(q.h)));
  list.push({id,w,h,x:Math.min(GC-w,Math.max(0,Math.round(q.x))),y:Math.min(500,Math.max(0,Math.round(q.y)))})}
 let yb=list.reduce((a,q)=>Math.max(a,q.y+q.h),0);
 for(const id of Object.keys(LB))if(!list.some(q=>q.id===id)){list.push({id,x:0,y:yb,w:DW[id]*3,h:LB[id].h});yb+=LB[id].h}
 return {v:3,b:layMap(layPack(list,null)),hide:[...new Set(hide)]}}
function layLoad(){
 try{const raw=localStorage.getItem(LKEY);if(!raw)return null;const r=layNorm(JSON.parse(raw));
  if(!r){localStorage.removeItem(LKEY);return null}
  if(JSON.stringify(r)!==raw)localStorage.setItem(LKEY,JSON.stringify(r));        // self-heal: store the repaired layout
  return r}catch(e){try{localStorage.removeItem(LKEY)}catch(x){}return null}}
function laySave(){try{if(!LAY)localStorage.removeItem(LKEY);else localStorage.setItem(LKEY,JSON.stringify(LAY))}catch(e){}}
const layWide=()=>matchMedia('(min-width:851px)').matches;
/* the standard layout, measured: where every block is now, in grid cells */
function layMeasure(){
 const o=LHOME.now.getBoundingClientRect(),st=(o.width+GG)/GC,b={};
 for(const id of Object.keys(LB)){const r=LEL[id].getBoundingClientRect();if(!r.width||!r.height)continue;
  b[id]={x:Math.round((r.left-o.left)/st),y:Math.round((r.top-o.top)/(GU+GG)),w:Math.round((r.width+GG)/st),h:Math.ceil((r.height+GG)/(GU+GG))}}
 if(b.inpc)b.inpc.h=Math.max(b.inpc.h,LB.inpc.h);      // the card is measured as drawn, and it is collapsed by default: keep room for the OPEN card (LB.inpc.h, measured: 4 rows console / studio, 5 rows stage at 860 px and wider)
 return layNorm({b,hide:[]})}
function layStyle(){
 for(const id of Object.keys(LB)){const p=LPOS&&LPOS[id];if(!p)continue;LEL[id].style.gridColumn=`${p.x+1} / span ${p.w}`;LEL[id].style.gridRow=`${p.y+1} / span ${p.h}`}}
function layPlace(){
 const custom=(LAY||LEDIT)&&layWide();
 let host=document.getElementById('lay');
 if(!custom){
  if(host)host.remove();document.body.classList.remove('lay-on');
  for(const id of Object.keys(LB)){LEL[id].classList.remove('lhid');LEL[id].style.gridColumn='';LEL[id].style.gridRow=''}
  LHOME.now.append(LEL.cl,LHOME.cuerow,LEL.inpc);LHOME.cuerow.append(LEL.fs,LEL.pv);LHOME.cols.append(LEL.libcol,LEL.plcol);return}
 if(!host){host=document.createElement('div');host.id='lay';LHOME.now.before(host)}
 for(const id of Object.keys(LB))if(LEL[id].parentNode!==host)host.append(LEL[id]);          // (not moved again when already there: that would reset a scrolled list)
 LPOS=LEDIT?LAY.b:layMap(layPack(layItems(LAY,false),null));
 layStyle();
 for(const id of Object.keys(LB))LEL[id].classList.toggle('lhid',LAY.hide.includes(id));
 document.body.classList.add('lay-on')}
function layCommit(list,fixed){LAY.b=layMap(layPack(layPack(list,fixed),null));LPOS=null;laySave();layPlace();layOverlay()}
const layWith=(id,n)=>layItems(LAY,true).map(q=>q.id===id?{...q,...n}:q);
function layNudge(id,d){
 const q=LAY.b[id],n={x:q.x,y:q.y};
 if(d==='l')n.x=Math.max(0,q.x-1);else if(d==='r')n.x=Math.min(GC-q.w,q.x+1);else if(d==='u')n.y=Math.max(0,q.y-1);else n.y=q.y+1;
 layCommit(layWith(id,n),id)}
function layPreset(id,w){const q=LAY.b[id];layCommit(layWith(id,{w,x:Math.min(q.x,GC-w)}),id)}
function layFitH(id){
 const el=LEL[id],st=[el.style.height,el.style.alignSelf,el.style.overflow];
 el.style.height='max-content';el.style.alignSelf='start';el.style.overflow='visible';
 const h=el.offsetHeight;[el.style.height,el.style.alignSelf,el.style.overflow]=st;
 layCommit(layWith(id,{h:Math.min(GMAXH,Math.max(GMINH,Math.ceil((h+GG)/(GU+GG))))}),id)}
function layHide(id){const k=LAY.hide.indexOf(id);if(k>=0)LAY.hide.splice(k,1);else LAY.hide.push(id);laySave();layPlace();layOverlay()}
/* drag to move, drag a handle to resize: snapped to the grid; the blocks in the way are pushed down while you drag */
function layDown(e,id,kind){
 if(!LEDIT||e.button>0)return;e.preventDefault();
 try{e.target.setPointerCapture(e.pointerId)}catch(x){}
 LOP={kind,id,px:e.clientX,py:e.clientY,o:{...LAY.b[id]},n:null};document.body.classList.add('lop')}
function layMoveEv(e){
 if(!LOP)return;const hr=document.getElementById('lay').getBoundingClientRect(),cs=(hr.width+GG)/GC,rs=GU+GG;
 const dx=Math.round((e.clientX-LOP.px)/cs),dy=Math.round((e.clientY-LOP.py)/rs),o=LOP.o,n={x:o.x,y:o.y,w:o.w,h:o.h};
 if(LOP.kind==='move'){n.x=Math.max(0,Math.min(GC-o.w,o.x+dx));n.y=Math.max(0,o.y+dy)}
 else{if(LOP.kind.includes('e'))n.w=Math.max(GMINW,Math.min(GC-o.x,o.w+dx));if(LOP.kind.includes('s'))n.h=Math.max(GMINH,Math.min(GMAXH,o.h+dy))}
 LOP.n=n;LPOS=layMap(layPack(layWith(LOP.id,n),LOP.id));layStyle();layOverlay()}
function layEnd(commit){
 if(!LOP)return;const {id,n}=LOP;LOP=null;document.body.classList.remove('lop');
 if(commit&&n)layCommit(layWith(id,n),id);else{LPOS=null;layPlace();layOverlay()}}
document.addEventListener('pointerdown',e=>{
 const h=e.target.closest&&e.target.closest('.ltb b,.lrz');if(!h||!LEDIT)return;
 if(h.classList.contains('lrz'))layDown(e,h.dataset.id,h.dataset.e);else layDown(e,h.closest('.ltb').dataset.id,'move')});
document.addEventListener('pointermove',layMoveEv);
document.addEventListener('pointerup',()=>layEnd(true));document.addEventListener('pointercancel',()=>layEnd(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&LOP){e.preventDefault();layEnd(false)}});
function layOverlay(){
 if(!LEDIT){document.querySelectorAll('.ltb,.lrz').forEach(e=>e.remove());return}
 for(const id of Object.keys(LB)){
  const el=LEL[id];let tb=document.querySelector(`.ltb[data-id=${id}]`);const hs=[...document.querySelectorAll(`.lrz[data-id=${id}]`)];
  if(!el.getClientRects().length){if(tb)tb.remove();hs.forEach(h=>h.remove());continue}
  const r=el.getBoundingClientRect(),hid=LAY.hide.includes(id),k=hid+':'+LAY.b[id].w;
  if(tb&&tb.dataset.k!==k&&!(LOP&&LOP.id===id&&LOP.kind==='move')){tb.remove();tb=null}
  if(!tb){tb=document.createElement('div');tb.className='ltb';tb.dataset.id=id;tb.dataset.k=k;
   tb.innerHTML=`<b title="Drag to move; it snaps to the grid">&#10303; ${LB[id].n}</b><button data-d=l title="Move left">&#9664;</button><button data-d=r title="Move right">&#9654;</button><button data-d=u title="Move up">&#9650;</button><button data-d=d title="Move down">&#9660;</button><button data-d=h title="${hid?'Show':'Hide'} this block">${hid?'&#128065;&#8260;':'&#128065;'}</button><span class=lsz>${LSZ.map(([n,t,h])=>`<button data-s=${n} title="${h}"${LAY.b[id].w===n?' class=on':''}>${t}</button>`).join('')}<button data-f=1 title="Fit the height to the content">&#8597;</button></span>`;
   document.body.append(tb)}
  tb.style.top=Math.max(2,r.top+4)+'px';tb.style.left='auto';tb.style.maxWidth=Math.max(150,r.width-12)+'px';tb.style.right=Math.max(4,innerWidth-r.right+6)+'px';
  if(!hs.length)for(const kd of ['e','s','se']){const h=document.createElement('div');h.className='lrz';h.dataset.id=id;h.dataset.e=kd;h.title='Drag to resize';document.body.append(h);hs.push(h)}
  for(const h of hs){const kd=h.dataset.e;
   h.style.left=(kd==='s'?r.left+r.width/2-22:r.right-(kd==='se'?12:7))+'px';h.style.top=(kd==='e'?r.top+r.height/2-22:r.bottom-(kd==='se'?12:7))+'px'}}}
function layEdit(){
 if(!layWide()){say('Layout editing is for wide screens (the page is narrower than 850 px).',false);return}
 try{settings.close()}catch(e){}
 LAYWAS=LAY;if(!LAY)LAY=layMeasure();if(!LAY){say('Could not read the page layout.',false);return}
 LAY0=JSON.stringify(LAY);
 LEDIT=true;document.body.classList.add('ledit');lebar.hidden=false;
 for(const id of Object.keys(LB))LEL[id].inert=true;
 layPlace();layOverlay();clearInterval(layT);layT=setInterval(layOverlay,400)}
function layDone(){
 layEnd(false);LEDIT=false;document.body.classList.remove('ledit');lebar.hidden=true;clearInterval(layT);
 for(const id of Object.keys(LB))LEL[id].inert=false;
 if(!LAYWAS&&LAY&&JSON.stringify(LAY)===LAY0)LAY=null;       // nothing was changed: stay on the standard layout
 laySave();layPlace();layOverlay()}
function layReset(){
 LAY=null;try{localStorage.removeItem(LKEY)}catch(e){}
 if(LEDIT){LAYWAS=null;layEnd(false);LEDIT=false;document.body.classList.remove('ledit');lebar.hidden=true;clearInterval(layT);for(const id of Object.keys(LB))LEL[id].inert=false}
 layPlace();layOverlay();try{settings.close()}catch(e){}}
document.addEventListener('click',e=>{const b=e.target.closest('.ltb button');if(!b||!LEDIT)return;const id=b.closest('.ltb').dataset.id;
 if(b.dataset.s)layPreset(id,+b.dataset.s);else if(b.dataset.f)layFitH(id);else if(b.dataset.d==='h')layHide(id);else layNudge(id,b.dataset.d)});
window.addEventListener('scroll',()=>{if(LEDIT)layOverlay()},{passive:true});let layWas=layWide();window.addEventListener('resize',()=>{if(LEDIT)layOverlay();const w=layWide();if(w!==layWas){layWas=w;layPlace()}});
/* export / import of the layout: a small JSON file (or pasted text). Imports are only ever stored after layNorm() has repaired them. */
const LXAPP='cue-media-engine-layout',LXOLD='companionplayer-layout',LXMAX=65536,LPREV='cp_layout_prev',LXSKIN=['console','studio','stage'],LXTHEME=['system','light','dark'];
let LUNDO=null,LIMP=null,liT=0;
const layDefault=()=>layNorm({b:layFromRows([['cl'],['fs','pv'],['inpc'],['libcol','plcol']],DW),hide:[]});
const lxName=s=>String(s==null?'':s).replace(/[\u0000-\u001f\u007f]+/g,' ').trim().slice(0,60);
const layOrdered=L=>({v:3,b:Object.fromEntries(Object.keys(LB).filter(id=>L.b[id]).map(id=>{const q=L.b[id];return [id,{x:q.x,y:q.y,w:q.w,h:q.h}]})),hide:L.hide.filter(id=>LB[id])});
/* the saved layout, or (standard layout) the measured one; on a narrow screen nothing can be measured, so the default grid stands in */
function layCurrent(){
 if(LAY)return {lay:LAY,std:false};
 let m=null;try{if(layWide())m=layMeasure()}catch(e){}
 return {lay:m||layDefault(),std:true}}
function lxAppear(a){
 if(!a||typeof a!=='object'||Array.isArray(a))return null;const r={};
 if(LXSKIN.includes(a.skin))r.skin=a.skin;if(LXTHEME.includes(a.theme))r.theme=a.theme;if(typeof a.waveforms==='boolean')r.waveforms=a.waveforms;
 return Object.keys(r).length?r:null}
function layAppear(a){if(a.skin)setLook('skin',a.skin);if(a.theme)setLook('theme',a.theme);if('waveforms' in a)setWave(a.waveforms)}
function layExportObj(name,withApp){
 const {lay,std}=layCurrent(),nm=lxName(name)||'layout';
 const obj={app:LXAPP,version:1,name:nm,exported:new Date().toISOString(),layout:layOrdered(lay)};
 if(withApp)obj.appearance={skin:LOOK.skin,theme:LOOK.theme,waveforms:WAVE};
 const fn='cue-media-engine-layout-'+(nm.replace(/[^\p{L}\p{N}_-]+/gu,'-').replace(/^-+|-+$/g,'').slice(0,40)||'layout')+'.json';
 return {obj,fn,std}}
function layExport(){
 lx_msg.textContent='';lx_msg.className='msg';lx_name.value='layout';lx_app.checked=false;
 const std=!LAY;lx_note.hidden=!std;
 if(std)lx_note.textContent='No custom layout is saved in this browser, so the standard layout (as it is on your screen now) will be exported.';
 lxdlg.showModal();lx_name.select()}
function layExportGo(){
 const {obj,fn,std}=layExportObj(lx_name.value,lx_app.checked);
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(obj,null,1)],{type:'application/json'}));a.download=fn;
 document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);
 lx_msg.textContent='Saved '+fn+(std?' (there is no custom layout, so this is the standard layout).':'.');lx_msg.className='msg ok'}
/* parse and validate an import; the result holds only repaired data, never the raw text */
function layParse(text){
 const bad=m=>({ok:false,msg:m});
 if(typeof text!=='string')return bad('Nothing to import.');
 if(new TextEncoder().encode(text).length>LXMAX)return bad('This is too large for a layout file (the limit is 64 KB). It was not read.');
 let o;try{o=JSON.parse(text)}catch(e){return bad('This is not valid JSON, so it cannot be a layout file. Check that the whole text was copied.')}
 if(!o||typeof o!=='object'||Array.isArray(o)||(o.app!==LXAPP&&o.app!==LXOLD))return bad('This is not a Cue Media Engine layout file (its "app" field does not match).');
 const v=o.version;
 if(typeof v!=='number'||!Number.isInteger(v)||v<1)return bad('This layout file has no valid version number.');
 if(v>1)return bad('This layout was made by a newer version of Cue Media Engine (file version '+v+'). Update this player to import it.');
 const lay=layNorm(o.layout);
 if(!lay)return bad('The file has no usable layout in it.');
 return {ok:true,name:lxName(o.name)||'(no name)',lay,app:lxAppear(o.appearance)}}
function liMsg(t,ok,undo){
 li_msg.textContent=t;li_msg.className='msg '+(ok?'ok':'bad');
 if(undo){const b=document.createElement('button');b.className='lundo';b.textContent='Undo import';b.onclick=layUndo;li_msg.append(b)}
 li_undo.hidden=!layUndoAvail()||!!undo}
function layUndoAvail(){
 if(LUNDO)return true;
 try{const u=JSON.parse(localStorage.getItem(LPREV)||'null');return !!u&&typeof u==='object'&&'lay' in u}catch(e){return false}}
function liClear(){LIMP=null;li_pv.hidden=true;li_go.disabled=true}
function liCheck(t){
 liClear();
 if(!t||!t.trim()){liMsg('',true);return}
 const r=layParse(t);
 if(!r.ok){liMsg(r.msg,false);return}
 LIMP=r;liMsg('',true);li_pv.hidden=false;li_go.disabled=false;
 li_name.textContent=r.name;
 const vis=layMap(layPack(layItems(r.lay,false),null)),H=Math.max(1,...Object.values(vis).map(q=>q.y+q.h)),row=Math.min(8,230/H);
 li_map.textContent='';li_map.style.height=Math.max(32,H*row)+'px';
 for(const id of Object.keys(vis)){const q=vis[id],d=document.createElement('div');
  d.style.left=q.x/GC*100+'%';d.style.top=q.y*row+'px';d.style.width=q.w/GC*100+'%';d.style.height=q.h*row+'px';d.textContent=LB[id].n;li_map.append(d)}
 const hid=r.lay.hide.map(id=>LB[id].n);
 li_hid.textContent=hid.length?'Hidden blocks: '+hid.join(', ')+'.':'No blocks are hidden.';
 li_appf.hidden=!r.app;li_app.checked=false;
 if(r.app)li_apptxt.textContent='Also apply appearance ('+[r.app.skin&&'skin '+r.app.skin,r.app.theme&&'theme '+r.app.theme,'waveforms' in r.app&&'waveforms '+(r.app.waveforms?'on':'off')].filter(Boolean).join(', ')+')';
 li_narrow.hidden=layWide()}
async function liFile(f){
 if(!f)return;
 if(f.size>LXMAX){li_txt.value='';liClear();liMsg('This file is too large for a layout (the limit is 64 KB). It was not read.',false);return}
 let t;try{t=await f.text()}catch(e){li_txt.value='';liClear();liMsg('The file could not be read.',false);return}
 li_txt.value=t;liCheck(t)}
function layImport(){
 li_txt.value='';li_file.value='';liClear();liMsg('',true);lidlg.classList.remove('drag');lidlg.showModal()}
li_file.addEventListener('change',()=>{liFile(li_file.files[0]);li_file.value=''});
li_txt.addEventListener('input',()=>{clearTimeout(liT);liT=setTimeout(()=>liCheck(li_txt.value),250)});
lidlg.addEventListener('dragover',e=>{e.preventDefault();lidlg.classList.add('drag')});
lidlg.addEventListener('dragleave',e=>{if(e.target===lidlg)lidlg.classList.remove('drag')});
lidlg.addEventListener('drop',e=>{e.preventDefault();lidlg.classList.remove('drag');
 const f=e.dataTransfer&&e.dataTransfer.files[0];if(f){liFile(f);return}
 const t=e.dataTransfer?e.dataTransfer.getData('text'):'';if(t){li_txt.value=t;liCheck(t)}});
/* make this layout the saved one (also while editing); false if the browser would not store it */
function layInstall(lay){
 LAY=lay;LPOS=null;
 if(LEDIT){LAYWAS=lay;if(!LAY){LAY=layDefault();LAY0=JSON.stringify(LAY)}else LAY0=''}
 let ok=true;
 try{if(lay){const s=JSON.stringify(lay);localStorage.setItem(LKEY,s);ok=localStorage.getItem(LKEY)===s}else localStorage.removeItem(LKEY)}catch(e){ok=false}
 layPlace();layOverlay();return ok}
function layApplyImport(){
 const r=LIMP;if(!r)return;
 const useApp=!!(r.app&&li_app.checked);
 LUNDO={lay:LAY?JSON.parse(JSON.stringify(LAY)):null,app:useApp?{skin:LOOK.skin,theme:LOOK.theme,waveforms:WAVE}:null};
 try{localStorage.setItem(LPREV,JSON.stringify(LUNDO))}catch(e){}
 const ok=layInstall(r.lay);
 if(useApp)layAppear(r.app);
 liClear();li_txt.value='';
 const t='Layout "'+r.name+'" '+(ok?(layWide()?'applied.':'saved. It will apply on a wider screen (over 850 px).'):'applied for this session, but this browser would not store it.')+(useApp?' Appearance applied.':'');
 liMsg(t,ok,true)}
function layUndo(){
 let u=LUNDO;
 if(!u){try{u=JSON.parse(localStorage.getItem(LPREV)||'null')}catch(e){u=null}}
 if(!u||typeof u!=='object'||!('lay' in u)){liMsg('There is nothing to undo.',false);return}
 const lay=u.lay?layNorm(u.lay):null,a=lxAppear(u.app);
 layInstall(lay);if(a)layAppear(a);
 LUNDO=null;try{localStorage.removeItem(LPREV)}catch(e){}
 liClear();liMsg('Import undone: the previous layout'+(a?' and appearance are':' is')+' back.',true)}
LAY=layLoad();layPlace();
/* first-visit guided tour: remembered per browser with the "never show again" box (cleared with the site data) */
//@include tour.js

let tourN=0;
const tourSeen=()=>{try{return localStorage.getItem('cp_tour')==='1'}catch(e){return false}};
function tourNever(v){try{if(v)localStorage.setItem('cp_tour','1');else localStorage.removeItem('cp_tour')}catch(e){}}
function tourClose(){const o=document.getElementById('tour');if(o){o.remove();pageUnlock()}document.removeEventListener('keydown',tourKey,true);window.removeEventListener('resize',tourLayout);window.removeEventListener('scroll',tourScroll,true);tourPrevFocus&&tourPrevFocus.focus&&tourPrevFocus.focus()}
let tourPrevFocus=null;
function tourKey(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();tourClose()}
 else if(e.key==='ArrowRight'){e.preventDefault();tourGo(1)}else if(e.key==='ArrowLeft'){e.preventDefault();tourGo(-1)}}
function tourGo(d){const n=tourN+d;if(n<0)return;if(n>=TOUR.length){tourClose();return}tourN=n;tourPlace()}
function tourPlace(){const o=document.getElementById('tour');if(!o)return;
 const st=TOUR[tourN];const el=st.s?document.querySelector(st.s):null;const vis=el&&el.getClientRects().length;
 if(vis)el.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
 const card=o.querySelector('.tcard');o.querySelector('.thole').style.transition='';
 const last=tourN===TOUR.length-1;
 const cb=o.querySelector('#tournever');const keep=cb?cb.checked:tourSeen();
 card.innerHTML=`<div class=tstep>Step ${tourN+1} of ${TOUR.length}</div><h3 id=tourh>${esc(st.t)}</h3><p>${esc(st.x)}</p>
  <label class=tnever><input type=checkbox id=tournever ${keep?'checked':''} onchange="tourNever(this.checked)"> Never show this again</label>
  <div class=trow><button onclick="tourClose()">${last?'Close':'Skip'}</button><span class=sp></span>${tourN?'<button onclick="tourGo(-1)">Back</button>':''}<button class=pri id=tournext onclick="tourGo(1)">${last?'Done':'Next'}</button></div>`;

 tourLayout(true);
 const nb=document.getElementById('tournext');if(nb)nb.focus()}
function tourLayout(anim){const o=document.getElementById('tour');if(!o)return;
 const st=TOUR[tourN];const el=st.s?document.querySelector(st.s):null;const vis=el&&el.getClientRects().length;
 const r=vis?el.getBoundingClientRect():null;const hole=o.querySelector('.thole'),card=o.querySelector('.tcard');
 if(r){const m=6;hole.style.cssText=`display:block;top:${r.top-m}px;left:${r.left-m}px;width:${r.width+2*m}px;height:${r.height+2*m}px`}
 else hole.style.cssText='display:block;top:50%;left:50%;width:0;height:0';
 if(!anim)hole.style.transition='none';
 const cw=card.offsetWidth,ch=card.offsetHeight,W=innerWidth,H=innerHeight;let x,y;
 if(!r){x=(W-cw)/2;y=(H-ch)/2}else{
  const below=H-r.bottom,above=r.top;
  if(below>=ch+20)y=r.bottom+16;else if(above>=ch+20)y=r.top-ch-16;else y=Math.max(12,Math.min(H-ch-12,r.top+16));
  x=Math.max(12,Math.min(W-cw-12,r.left+12));
  if(r.height>H*.7&&below<ch+20&&above<ch+20){x=Math.max(12,Math.min(W-cw-12,r.right-cw-24));y=Math.max(12,Math.min(H-ch-12,(H-ch)/2))}}
 card.style.left=Math.max(8,x)+'px';card.style.top=Math.max(8,y)+'px'}
let tourRaf=0;
function tourScroll(){if(tourRaf)return;tourRaf=requestAnimationFrame(()=>{tourRaf=0;const o=document.getElementById('tour');if(!o)return;o.querySelector('.thole').style.transition='none';tourLayout()})}
function startTour(){if(document.getElementById('tour'))return;
 try{if(settings.open)settings.close()}catch(e){}
 tourPrevFocus=document.activeElement;tourN=0;
 const o=document.createElement('div');o.id='tour';o.setAttribute('role','dialog');o.setAttribute('aria-modal','true');o.setAttribute('aria-labelledby','tourh');
 o.innerHTML='<div class=tshade></div><div class=thole></div><div class=tcard></div>';document.body.appendChild(o);
 pageLock();o.querySelector('.tshade').onclick=()=>{};document.addEventListener('keydown',tourKey,true);window.addEventListener('resize',tourLayout);window.addEventListener('scroll',tourScroll,true);
 window.scrollTo(0,0);tourPlace()}
if(!tourSeen())setTimeout(startTour,800);
loadDevs();render(true);
async function renderLoop(){try{await render()}catch(e){healthSync({status:'error',state:'problem',summary:'Cannot reach the player',detail:'cannot reach the player',checks:[]})}setTimeout(renderLoop,1000)}   // one render at a time: a slow reply cannot overlap the next
setTimeout(renderLoop,1000);liveOpen();
pinUi();try{fillPvTarget()}catch(e){}pvmSync();fitInf();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitInf);
