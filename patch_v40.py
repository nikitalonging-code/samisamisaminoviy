from pathlib import Path

for name in ['index.html','app.html']:
    p=Path('/mnt/data/v40fix/frontend')/name
    s=p.read_text(encoding='utf-8')
    css=r'''
<style id="v40-final-layout-case-rocket">
/* CRASH/ROCKET: keep controls inside the 390px app viewport, not the desktop viewport. */
#rocketScreen .bet-btn,
#rocketScreen .cashout-btn{
  position:absolute !important;
  left:16px !important;
  right:16px !important;
  bottom:14px !important;
  width:auto !important;
  max-width:none !important;
  margin:0 !important;
  z-index:4200 !important;
}
#rocketScreen .bets-list{padding-bottom:92px !important;}

/* CASES: make the reel always visible and above surrounding content. */
#caseScreen .case-reel-wrap{position:relative!important;display:none;min-height:168px;z-index:40!important;}
#caseScreen .case-reel-wrap.active{display:block!important;visibility:visible!important;opacity:1!important;}
#caseScreen .case-reel{display:flex!important;align-items:center!important;height:100%!important;min-width:max-content!important;will-change:transform!important;transition-property:transform!important;}
#caseScreen .case-reel-wrap .case-reel-pointer{z-index:50!important;}
#promoCodeModal{z-index:10000!important;}
#promoCodeModal.active{display:flex!important;visibility:visible!important;opacity:1!important;}
</style>
'''
    s=s.replace('</head>', css+'\n</head>',1)
    script=r'''
<script id="v40-runtime-hardfix">
(function(){
  const API=(window.__APP_CONFIG__?.apiBase||'').replace(/\/$/,'');
  const tg=window.Telegram?.WebApp;
  const uid=()=>String(tg?.initDataUnsafe?.user?.id||'');
  const headers=()=>({'X-Telegram-User-Id':uid(),'Content-Type':'application/json'});

  // ---- Rocket layout/open fix ----
  document.addEventListener('click',(e)=>{
    const r=e.target?.closest?.('#playHubRocketBtn,.rocket-game-card,#openRocketBtn');
    if(!r) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const screen=document.getElementById('rocketScreen');
    document.getElementById('playHubScreen')?.classList.remove('active');
    if(screen){
      screen.classList.add('active');
      screen.style.display='flex';
      screen.style.position='absolute';
      screen.style.inset='0';
      screen.scrollTop=0;
    }
    try{ window.__rocketOpen?.(); }catch(_){ }
    try{ window.__syncCrashRound?.(); }catch(_){ }
  },true);

  // ---- Standalone case opener. Stop all legacy handlers so one click = one flow. ----
  const caseConfigs={
    promo:{name:'Promo Case',price:0,promo:true,art:'https://cdn.changes.tg/gifts/models/Heart%20Locket/png/Original.png'},
    summer:{name:'Summer Case',price:1,promo:false,art:'https://cdn.changes.tg/gifts/models/Stellar%20Rocket/png/Original.png'}
  };
  const prizes=[
    {type:'ton',name:'0 TON',value:0},
    {type:'ton',name:'0.3 TON',value:.3},
    {type:'ton',name:'0.5 TON',value:.5},
    {type:'ton',name:'1 TON',value:1},
    {type:'nft',name:'Lol Pop',floor:3.35,img:'https://cdn.changes.tg/gifts/models/Lol%20Pop/png/Original.png'},
    {type:'nft',name:'Santa Hat',floor:3.31,img:'https://cdn.changes.tg/gifts/models/Santa%20Hat/png/Original.png'},
    {type:'nft',name:'Cookie Heart',floor:4.20,img:'https://cdn.changes.tg/gifts/models/Cookie%20Heart/png/Original.png'},
    {type:'nft',name:'Homemade Cake',floor:4.08,img:'https://cdn.changes.tg/gifts/models/Homemade%20Cake/png/Original.png'},
    {type:'nft',name:'Jelly Bunny',floor:7.30,img:'https://cdn.changes.tg/gifts/models/Jelly%20Bunny/png/Original.png'}
  ];
  function weightedPrize(){
    const r=Math.random()*100;
    if(r<28) return prizes[0];
    if(r<58) return prizes[1];
    if(r<78) return prizes[2];
    if(r<99) return prizes[3];
    return prizes[4+Math.floor(Math.random()*5)];
  }
  function openCaseUI(type){
    const cfg=caseConfigs[type]||caseConfigs.summer;
    const s=document.getElementById('caseScreen'); if(!s)return;
    s.classList.add('active'); s.style.display='flex'; s.style.zIndex='9000';
    const title=s.querySelector('.case-top-title'); if(title) title.textContent=cfg.name;
    const hero=s.querySelector('.case-hero-art'); if(hero){hero.src=cfg.art;hero.style.display='block';}
    const n=s.querySelector('.case-hero-name'); if(n)n.textContent=cfg.name;
    const pr=s.querySelector('.case-price'); if(pr)pr.textContent=cfg.promo?'0 TON':'1 TON';
    const sub=s.querySelector('.case-hero-sub'); if(sub)sub.textContent=cfg.promo?'Бесплатно. Нужен промокод администратора.':'Открытие стоит 1 TON';
    const btn=document.getElementById('caseOpenBtn');
    if(btn){btn.disabled=false;btn.dataset.caseType=cfg.name;btn.dataset.casePrice=String(cfg.price);btn.dataset.casePromo=cfg.promo?'1':'';btn.textContent=cfg.promo?'🎟️ Ввести промокод':'🎁 Открыть за 1 TON';}
    if(!cfg.promo){
      try{window.__renderCasePossible?.();window.__renderCasePossibleReal?.();}catch(_){ }
      fetch(API+'/api/me',{headers:{'X-Telegram-User-Id':uid()},cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{if(d){window.__serverBalance=Number(d.balance||0);window.__syncBalance?.(window.__serverBalance);const cb=document.getElementById('caseBalanceVal');if(cb)cb.textContent=window.__serverBalance.toFixed(3);}}).catch(()=>{});
    }
  }
  document.addEventListener('click',(e)=>{
    const card=e.target?.closest?.('.case-card');
    if(card){e.preventDefault();e.stopImmediatePropagation();openCaseUI(card.dataset.case||'summer');return;}
  },true);

  function promoOpen(){
    const m=document.getElementById('promoCodeModal');
    if(m){m.classList.add('active');m.style.display='flex';m.style.zIndex='10000';setTimeout(()=>document.getElementById('promoCodeInput')?.focus(),0);}
  }
  async function openSummer(){
    const reelWrap=document.getElementById('caseReelWrap'), reel=document.getElementById('caseReel');
    const btn=document.getElementById('caseOpenBtn');
    let bal=Number(window.__serverBalance);
    if(!Number.isFinite(bal)) bal=Number(document.getElementById('caseBalanceVal')?.textContent||0);
    if(bal<1){const er=document.getElementById('caseInsufficient');if(er)er.textContent='Недостаточно TON. Нужно 1 TON.';return;}
    btn.disabled=true;
    const winner=weightedPrize();
    // Reserve locally immediately for responsive UI; server charge confirms in background.
    window.__serverBalance=bal-1; window.__syncBalance?.(bal-1); const cb=document.getElementById('caseBalanceVal'); if(cb)cb.textContent=(bal-1).toFixed(3);
    reel.innerHTML='';
    const arr=[]; for(let i=0;i<36;i++) arr.push(prizes[(i*3+i%7)%prizes.length]); const winIndex=29; arr[winIndex]=winner;
    arr.forEach(p=>{const c=document.createElement('div');c.className='reel-card';c.innerHTML=p.type==='nft'?`<img src="${p.img}" alt=""><strong>${p.name}</strong><span>NFT</span>`:`<div class="reel-ton-wrap"><span class="case-ton-icon">▽</span></div><strong>${p.name}</strong><span>${p.name}</span>`;reel.appendChild(c);});
    reelWrap.classList.add('active'); reel.style.transition='none'; reel.style.transform='translate3d(0,0,0)'; void reel.offsetWidth;
    requestAnimationFrame(()=>{const step=118, viewport=reelWrap.clientWidth||330, cardW=108; const target=-(winIndex*step-(viewport/2-cardW/2)); reel.style.transition='transform 2.15s cubic-bezier(.12,.78,.18,1)'; reel.style.transform=`translate3d(${target}px,0,0)`;});
    const charge=fetch(API+'/api/wallet/charge',{method:'POST',headers:headers(),body:JSON.stringify({amount:1,reason:'Summer Case'}),cache:'no-store'}).then(r=>r.ok?r.json().then(x=>({ok:true,data:x})):r.text().then(t=>({ok:false,error:t||'Ошибка'}))).catch(e=>({ok:false,error:e.message||'Ошибка'}));
    setTimeout(async()=>{
      const cr=await charge;
      if(!cr.ok){window.__serverBalance=bal;window.__syncBalance?.(bal);if(cb)cb.textContent=bal.toFixed(3);reelWrap.classList.remove('active');if(btn)btn.disabled=false;const er=document.getElementById('caseInsufficient');if(er)er.textContent='Не удалось списать TON.';return;}
      setTimeout(()=>{
        const result=document.getElementById('caseResult'), img=document.getElementById('resultImage'), rp=document.getElementById('resultPrize'), rn=document.getElementById('resultNote');
        if(winner.type==='nft'){img.src=winner.img;img.style.display='block';rp.textContent=winner.floor.toFixed(2)+' TON';rn.textContent='NFT: '+winner.name;} else {img.style.display='none';rp.textContent=winner.name;rn.textContent=winner.value>0?'Вы получили '+winner.value.toFixed(2)+' TON':'В этот раз приз не выпал.';}
        result?.classList.add('active'); reelWrap.classList.remove('active'); btn.disabled=false;
      },350);
    },2200);
  }
  document.addEventListener('click',(e)=>{
    const b=e.target?.closest?.('#caseOpenBtn'); if(!b)return;
    e.preventDefault(); e.stopImmediatePropagation();
    if(b.dataset.casePromo==='1') promoOpen(); else openSummer();
  },true);

  // Balance inside modes always opens the top-up modal.
  document.addEventListener('click',(e)=>{
    const b=e.target?.closest?.('#rocketScreen .rk-balance-pill,#caseScreen .case-balance,#upgradeScreen .upgrade-balance');
    if(!b)return; e.preventDefault(); e.stopImmediatePropagation(); document.getElementById('topupBtn')?.click();
  },true);
})();
</script>
'''
    s=s.replace('</body>', script+'\n</body>',1)
    p.write_text(s,encoding='utf-8')
