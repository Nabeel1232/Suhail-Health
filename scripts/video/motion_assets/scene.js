/* Authored Suhail motion illustrations. Deterministic timeline; no network/API. */
(() => {
  const canvas = document.querySelector('canvas');
  const c = canvas.getContext('2d');
  const C = {cream:'#f5f6f3',ink:'#112e35',teal:'#086c68',deep:'#103b40',gold:'#c2a36d',muted:'#627b79',mint:'#dfede5',line:'#d7e3dd'};
  let config, logo;
  const clamp = n => Math.min(1,Math.max(0,n));
  const ease = n => 1-Math.pow(1-clamp(n),3);
  const smooth = n => {n=clamp(n);return n*n*(3-2*n);};
  const mix = (a,b,p) => a+(b-a)*p;
  const opacity = (t,start,end,fade=.75) => smooth((t-start)/fade)*smooth((end-t)/fade);

  function round(x,y,w,h,r=20,fill,stroke,width=1) {
    c.beginPath();c.roundRect(x,y,w,h,r);
    if(fill){c.fillStyle=fill;c.fill();}
    if(stroke){c.lineWidth=width;c.strokeStyle=stroke;c.stroke();}
  }
  function text(value,x,y,size=28,color=C.ink,weight=500,font='DM Sans',align='left') {
    c.font=`${weight} ${size}px "${font}"`;c.fillStyle=color;c.textAlign=align;c.textBaseline='alphabetic';c.fillText(value,x,y);
  }
  function lines(values,x,y,size=28,color=C.ink,weight=500,gap=1.25,font='DM Sans') {
    values.forEach((value,i)=>text(value,x,y+i*size*gap,size,color,weight,font));
  }
  function pill(value,x,y,w,fill=C.mint,color=C.teal,size=21) {
    round(x,y,w,44,22,fill);text(value,x+w/2,y+29,size,color,600,'DM Sans','center');
  }
  function path(points,color=C.teal,width=3,dashed=false) {
    c.beginPath();c.moveTo(...points[0]);for(const p of points.slice(1))c.lineTo(...p);c.strokeStyle=color;c.lineWidth=width;
    c.setLineDash(dashed?[10,11]:[]);c.stroke();c.setLineDash([]);
  }
  function icon(kind,x,y,size=48,color=C.teal) {
    c.save();c.translate(x,y);c.scale(size/48,size/48);c.strokeStyle=color;c.lineWidth=2.6;c.lineCap='round';c.lineJoin='round';
    const stroke=()=>c.stroke();
    if(kind==='file') {round(11,5,27,37,4,null,color,2.6);path([[18,17],[31,17]],color,2.6);path([[18,24],[31,24]],color,2.6);path([[18,31],[27,31]],color,2.6);}
    if(kind==='route'){path([[8,9],[8,37],[38,37]],color,2.6);path([[8,24],[34,24],[34,10]],color,2.6);path([[28,16],[34,10],[40,16]],color,2.6);}
    if(kind==='shield'){c.beginPath();c.moveTo(24,5);c.lineTo(40,12);c.lineTo(38,29);c.quadraticCurveTo(35,39,24,44);c.quadraticCurveTo(13,39,10,29);c.lineTo(8,12);c.closePath();stroke();path([[24,16],[24,27]],color,2.6);c.beginPath();c.arc(24,33,1.2,0,7);stroke();}
    if(kind==='message'){round(6,8,36,28,8,null,color,2.6);path([[13,36],[13,43],[23,36]],color,2.6);path([[15,18],[33,18]],color,2.6);path([[15,25],[27,25]],color,2.6);}
    if(kind==='network'){path([[24,15],[24,26],[10,26],[10,33]],color,2.6);path([[24,26],[38,26],[38,33]],color,2.6);round(17,3,14,12,3,null,color,2.6);round(3,34,14,11,3,null,color,2.6);round(31,34,14,11,3,null,color,2.6);}
    if(kind==='check'){c.beginPath();c.arc(24,24,19,0,7);stroke();path([[14,24],[21,31],[34,17]],color,2.8);}
    if(kind==='person'){c.beginPath();c.arc(24,14,9,0,7);stroke();c.beginPath();c.moveTo(7,43);c.quadraticCurveTo(7,28,24,28);c.quadraticCurveTo(41,28,41,43);stroke();}
    if(kind==='team'){c.beginPath();c.arc(21,14,8,0,7);stroke();c.beginPath();c.arc(36,19,6,0,7);stroke();c.beginPath();c.moveTo(5,42);c.quadraticCurveTo(5,28,21,28);c.quadraticCurveTo(37,28,37,42);stroke();c.beginPath();c.moveTo(36,31);c.quadraticCurveTo(46,31,46,42);stroke();}
    if(kind==='building'){round(8,7,32,37,3,null,color,2.6);path([[18,44],[18,32],[30,32],[30,44]],color,2.6);[[16,16],[29,16],[16,24],[29,24]].forEach(([a,b])=>round(a,b,4,4,1,color));}
    c.restore();
  }
  function logoAt(x,y,w,alpha=1){c.save();c.globalAlpha*=alpha;c.drawImage(logo,x,y,w,w*logo.height/logo.width);c.restore();}
  function group(alpha,draw,slide=0){if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.translate(0,slide);draw();c.restore();}
  function background(t,dark=false){
    c.fillStyle=dark?C.deep:C.cream;c.fillRect(0,0,1920,1080);
    const glow=c.createRadialGradient(1640+Math.sin(t*.1)*35,170,0,1640,170,900);
    glow.addColorStop(0,dark?'#27676570':'#e0ebe3');glow.addColorStop(1,dark?'#103b4000':'#f5f6f300');c.fillStyle=glow;c.fillRect(0,0,1920,1080);
    c.save();c.globalAlpha=dark?.09:.2;c.strokeStyle=dark?'#9abdb7':'#bdcfc5';c.lineWidth=1;
    for(let x=0;x<1920;x+=80){c.beginPath();c.moveTo(x,85);c.lineTo(x,930);c.stroke();}
    for(let y=110;y<940;y+=80){c.beginPath();c.moveTo(75,y);c.lineTo(1845,y);c.stroke();}c.restore();
  }
  function authored(label,dark=false){
    text(label,1818,112,17,dark?'#adc9c3':'#718b82',650,'DM Sans','right');
    c.beginPath();c.arc(1829,106,3,0,7);c.fillStyle=C.gold;c.fill();
  }
  function brandLockup(){text('SUHAIL HEALTH',98,121,25,C.ink,750,'Manrope');path([[98,141],[220,141]],C.gold,3);}

  function solution(t){
    const q=t/config.duration*34;background(t);authored('AUTHORED SOLUTION ILLUSTRATION');
    group(opacity(q,0,6.2,.8),()=>{
      logoAt(164,218,350);pill('SCREENING → CARE',642,230,290);
      lines(['A result is only','the beginning.'],636,395,83,C.ink,750,1.18,'Manrope');
      text('Help each person reach an evidenced next step.',641,646,30,C.muted);
      path([[642,701],[1170,701]],C.line,3);c.beginPath();c.arc(1170,701,7,0,7);c.fillStyle=C.gold;c.fill();
    },18*(1-ease(q/1.5)));
    group(opacity(q,6.15,13.7,.6),()=>{
      brandLockup();lines(['The gaps are between','the steps.'],98,278,65,C.ink,750,1.18,'Manrope');
      text('A result, a referral and a visit are different facts.',102,473,28,C.muted);
      const nodes=[['file','Screening result','A result is available'],['route','Referral','Responsibility is proposed'],['building','Appointment','A visit may be booked'],['check','Care endpoint','Evidence still matters']];
      nodes.forEach((node,i)=>{
        const x=134+i*454,p=ease((q-5.8-i*.45)/1.2);
        if(i<3)path([[x+160,607],[x+390,607]],'#c9d6ce',3,true);
        group(p,()=>{round(x,540,90,90,25,'#fff',C.line);icon(node[0],x+21,561,48);text(node[1],x,689,27,C.ink,700,'Manrope');text(node[2],x,731,21,C.muted);},18*(1-p));
      });
      ['Missed handoffs','Unclear ownership','Unfinished follow-up'].forEach((value,i)=>pill(value,186+i*530,818,410,'#f0e9da','#8a7247',22));
    });
    group(opacity(q,13.72,22,.6),()=>{
      brandLockup();lines(['One shared journey.','A clear next owner.'],98,278,65,C.ink,750,1.18,'Manrope');
      text('Source facts, accountable work and reviewed evidence stay connected.',102,472,27,C.muted);
      const points=[280,736,1192,1648],labels=['Result received','Patient understands','Service accepts','Endpoint evidenced'];
      const progress=ease((q-13.4)/4.9);
      path([[points[0],630],[points[3],630]],'#d6e3da',7);path([[points[0],630],[mix(points[0],points[3],progress),630]],C.teal,7);
      points.forEach((x,i)=>{
        const p=ease((q-13.4-i*.9)/.8);round(x-45,585,90,90,45,p>.9?C.teal:'#fff',p>.9?C.teal:C.line,2);icon(i===0?'file':i===1?'person':i===2?'building':'check',x-24,606,48,p>.9?'#fff':C.teal);text(labels[i],x,738,25,C.ink,650,'Manrope','center');
      });
      pill('Human review',582,819,265);pill('Retained source evidence',874,819,390,'#e9eadb','#827044');
    });
    group(opacity(q,22.02,29.5,.6),()=>{
      brandLockup();lines(['Built around the patient.','Connected across the care team.'],98,265,59,C.ink,750,1.2,'Manrope');
      const cards=[['person','Patients','Understand the next step.','Ask questions and get support.'],['team','Care teams','See who owns the work.','Review and resolve unfinished care.'],['building','Receiving services','Accept the agreed responsibility.','Return appointment and source facts.']];
      cards.forEach((card,i)=>{const p=ease((q-21.5-i*.42)/1.1),x=98+i*582;
        group(p,()=>{round(x,447,550,337,24,'#fff',C.line);round(x+30,479,73,73,19,'#edf4ed');icon(card[0],x+43,492,48);text(card[1],x+32,615,34,C.ink,700,'Manrope');lines(card.slice(2),x+32,676,22,C.muted,450,1.65);},24*(1-p));
      });
      text('Accountable ownership   ·   Visible unfinished work   ·   Reviewed source evidence',960,861,23,C.teal,550,'DM Sans','center');
    });
    group(opacity(q,29.52,35,.6),()=>{
      brandLockup();pill('FROM SCREENING TO CARE',98,244,384);
      lines(['Guiding every result','to the right next step.'],98,409,75,C.ink,750,1.2,'Manrope');
      text('With the authorized care team in control.',103,666,29,C.muted);
      logoAt(1445,294,290);pill('Fictional demonstration · Human-authorized decisions',99,789,690,'#e9eee4',C.teal,23);
    });
  }

  function metric(layer){return layer.evaluated?`${layer.passed}/${layer.evaluated}`:'—';}
  function agents(t){
    const capabilities=config.metricsMode==='capabilities';
    const q=t/config.duration*35;background(t,true);authored('AUTHORED AGENT EXPLAINER',true);
    text('SIX BOUNDED AGENTS',98,149,23,'#bcd5ca',650);path([[98,173],[267,173]],C.gold,3);
    lines(['Different roles.','One accountable workflow.'],98,254,59,'#f3f5ec',750,1.16,'Manrope');
    text(capabilities?'Source-linked intelligence. Human-governed actions.':'Known synthetic function conformance',102,419,25,'#afccc2');
    const totals=config.evidence.totals;
    if(capabilities){
      round(1341,192,478,223,24,'#1a4a4c','#38615e');
      text('GPT-OSS 120B',1375,260,43,'#f3ead4',750,'Manrope');
      text('via Groq',1376,305,27,'#d4e3d8');
      text('1 configured model · 6 focused functions',1376,353,19,'#c7dacb');
      text('Modular model adapter',1376,391,21,'#acc7b9');
    }else if(totals){
      const passed=totals.primary.passed+totals.audit.passed,total=totals.primary.evaluated+totals.audit.evaluated;
      round(1341,192,478,223,24,'#1a4a4c','#38615e');text(`${passed}/${total}`,1375,282,65,'#f3ead4',750,'Manrope');
      text('saved function cases',1376,325,23,'#d4e3d8');text(`Primary scored ${metric(totals.primary)}`,1376,367,20,'#acc7b9');text(`Post-hoc audit ${metric(totals.audit)}`,1376,396,19,'#acc7b9');
    }
    const focus=q<7?-1:Math.min(5,Math.floor((q-7)/3.85));
    const capabilityDetails={
      intake:['Extract available facts','Flag what is missing'],
      pathway_router:['Map supported pathways','Surface uncertainty'],
      safety_escalation:['Preserve trusted alerts','Route qualified review'],
      patient_navigator:['Explain the next action','Keep the human reply'],
      coordination:['Prepare scoped referrals','Recover disrupted visits'],
      closure_evidence:['Link current sources','Expose open requirements'],
    };
    config.functions.forEach((agent,i)=>{
      const p=ease((q-.7-i*.5)/1.1),x=98+(i%3)*582,y=466+Math.floor(i/3)*191;
      const active=i===focus,pulse=active?(.6+.4*Math.sin(q*2.2)):0;
      const joinedPassed=agent.primary.passed+agent.audit.passed,joinedTotal=agent.primary.evaluated+agent.audit.evaluated;
      group(p,()=>{
        c.save();if(active){c.shadowColor='#c2a36d50';c.shadowBlur=17+8*pulse;}
        round(x,y,550,170,19,active?'#215554':'#19484a',active?C.gold:'#38615e',active?2.5:1);c.restore();
        round(x+21,y+21,46,46,13,active?'#c2a36d':'#2a5c58');icon(agent.icon,x+30,y+30,29,active?C.deep:'#d0e5d6');
        text(agent.name,x+82,y+53,28,'#f1f4eb',700,'Manrope');
        text(agent.purpose,x+23,y+96,21,'#b2cec1');
        text(capabilities?String(i+1).padStart(2,'0'):joinedTotal?`${joinedPassed}/${joinedTotal}`:'Not evaluated',x+520,y+68,capabilities?33:joinedTotal?48:22,capabilities?'#9fc4b2':joinedPassed<joinedTotal?'#e0bf7d':'#deebd8',750,'Manrope','right');
        path([[x+23,y+116],[x+527,y+116]],'#3a625c',1);
        text(capabilities?capabilityDetails[agent.id][0]:`Primary scored ${metric(agent.primary)}`,x+23,y+147,17,'#c2d8cb',550);
        text(capabilities?capabilityDetails[agent.id][1]:`Post-hoc audit ${metric(agent.audit)}`,x+527,y+147,17,!capabilities&&agent.audit.passed<agent.audit.evaluated?'#e0bf7d':'#c2d8cb',550,'DM Sans','right');
      },20*(1-p));
    });
    text(capabilities?'Six focused functions · Source-linked proposals · Persistent workflow state':'Small known-family synthetic set · Primary scoring + separate saved-response audit',98,884,21,'#c4d9ca');
    const errors=config.evidence.original_primary_scoring_errors;
    text(capabilities?'A model upgrade can be evaluated while care ownership and clinical gates stay governed.':(Number.isInteger(errors)?`${errors} original primary scoring errors retained · `:'Original run failures remain recorded · ')+'Not clinical accuracy or patient-outcome evidence.',98,921,20,'#b1cbbd');
  }

  function models(t){
    const q=t/config.duration*28;
    background(t);authored('AUTHORED MODEL-LAYER ILLUSTRATION');brandLockup();
    lines(['One intelligence layer.','Six focused care functions.'],98,262,64,C.ink,750,1.18,'Manrope');
    text('Model configuration stays separate from care workflow rules.',102,391,27,C.muted);
    const nodes=config.functions;
    nodes.forEach((agent,i)=>{
      const x=98+(i%3)*226,y=470+Math.floor(i/3)*179;
      const enter=ease((q-.6-i*.4)/1.2),focus=q>5&&Math.floor((q-5)/2.5)%6===i;
      group(enter,()=>{
        round(x,y,196,129,19,'#fff',focus?'#82ada0':C.line,focus?2:1);
        round(x+17,y+17,43,43,12,focus?'#d9eadf':'#edf4ed');icon(agent.icon,x+24,y+24,29,C.teal);
        text(agent.name,x+17,y+99,22,C.ink,650,'Manrope');
      },17*(1-enter));
    });
    group(ease((q-3)/1.3),()=>{
      path([[779,535],[827,535],[827,648],[880,648]],'#aac5b7',3);
      path([[779,714],[827,714],[827,648]],'#aac5b7',3);
      round(880,543,300,211,23,'#edf4ed','#aecbbb',1.5);
      icon('network',1001,567,58,C.teal);
      text('Model adapter',1030,668,30,C.ink,700,'Manrope','center');
      text('Source-linked proposals',1030,711,20,C.muted,500,'DM Sans','center');
      path([[1180,648],[1340,648]],C.teal,4);
      path([[1326,638],[1340,648],[1326,658]],C.teal,3);
      const p=((q-3)*.22)%1;
      if(p>=0){c.beginPath();c.arc(mix(1188,1320,p),648,6,0,7);c.fillStyle=C.gold;c.fill();}
    });
    group(ease((q-4)/1.3),()=>{
      round(1340,478,480,277,24,C.deep,'#38615e');
      pill('CURRENT CONFIGURATION',1367,504,310,'#2a5c58','#d7e7da',17);
      text('GPT-OSS 120B',1371,616,42,'#f3ead4',750,'Manrope');
      text('via Groq',1373,665,29,'#d2e4d6');
      text('1 configured model',1373,716,21,'#b2cec1');
    });
    group(ease((q-14)/1.2),()=>{
      path([[1580,756],[1580,806]],'#8cae9b',2.5,true);
      round(1340,807,480,97,20,'#fff','#d5dfd5',1.5);
      text('Future model integration + evaluation',1363,846,22,C.teal,650,'DM Sans');
      text('A separately measured upgrade path',1363,879,19,C.muted,450);
    },13*(1-ease((q-14)/1.2)));
    text('Care ownership · Evidence validation · Authorized clinical decisions',98,922,23,C.teal,550);
  }

  window.initialize = async input => {
    config=input;
    await Promise.all(Object.entries(input.fonts).map(async([name,url])=>{const face=new FontFace(name,`url(${url})`,{weight:'100 900'});await face.load();document.fonts.add(face);}));
    logo=new Image();await new Promise((resolve,reject)=>{logo.onload=resolve;logo.onerror=reject;logo.src=input.logo;});
  };
  window.motionFrame=(t,mime='image/png')=>{
    c.resetTransform();c.globalAlpha=1;c.setLineDash([]);
    config.scene==='solution'?solution(t):config.scene==='models'?models(t):config.scene==='closing'?
      window.suhailClosingScene(t,{config,c,C,background,authored,brandLockup,group,opacity,ease,round,text,lines,pill,path,icon,logoAt}):agents(t);
    return canvas.toDataURL(mime,.96);
  };
})();
