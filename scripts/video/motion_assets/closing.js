/* Authored closing illustration. Counts are supplied by validated saved evidence. */
window.suhailClosingScene = (t, h) => {
  const {config, c, C, background, authored, brandLockup, group, opacity, ease,
    round, text, lines, pill, path, icon, logoAt} = h;
  const q=t/config.duration*31;
  const record=config.software;
  background(t,q<9.1||q>19.1);
  authored('AUTHORED PRODUCT CLOSING',q<9.1||q>19.1);

  group(opacity(q,0,9.1,.7),()=>{
    text('VERIFIED WORKFLOW',98,149,23,'#bcd5ca',650);
    path([[98,173],[335,173]],C.gold,3);
    lines(['Software checks.','Recorded results.'],98,297,69,'#f3f5ec',750,1.17,'Manrope');
    text(`${record.passed.toLocaleString('en-GB')} / ${record.selected.toLocaleString('en-GB')}`,
      98,643,114,'#f3ead4',750,'Manrope');
    text('DETERMINISTIC SOFTWARE CHECKS PASSED',103,715,26,'#c9dfd0',650);
    text('Persisted workflow trajectories and invalid-closure checks.',103,765,26,'#b2cec1');
    round(1288,427,531,329,27,'#1a4a4c','#38615e');
    round(1323,465,68,68,18,'#2a5c58');icon('check',1335,477,44,'#d9eadf');
    text(String(record.model_calls),1324,625,78,'#f3ead4',750,'Manrope');
    text('model calls in these checks',1328,674,25,'#d4e3d8');
    text('A software measurement',1328,719,21,'#b2cec1');
    text('Human clinical oversight stays central.',98,899,26,'#c4d9ca');
  });

  group(opacity(q,9.1,19.1,.7),()=>{
    brandLockup();
    lines(['Evidence you can inspect.','An execution history you can follow.'],98,281,59,C.ink,750,1.2,'Manrope');
    const cards=[
      ['file','Source provenance','Source and model versions','Recorded inputs and outputs'],
      ['network','Execution archive','Actual case-level records','Separate evidence layers'],
      ['shield','Governed operation','Scoped access and ownership','Explicit spending limits'],
    ];
    cards.forEach((card,i)=>{
      const enter=ease((q-9.2-i*.4)/1.1),x=98+i*582;
      group(enter,()=>{
        round(x,478,550,309,24,'#fff',C.line);
        round(x+30,508,66,66,18,'#edf4ed');icon(card[0],x+42,520,42,C.teal);
        text(card[1],x+31,633,32,C.ink,700,'Manrope');
        lines(card.slice(2),x+31,689,23,C.muted,450,1.65);
      },21*(1-enter));
    });
    text('A shared workflow. Source-supported decisions. An accountable care team.',98,884,26,C.teal,550);
  });

  group(opacity(q,19.1,32,.7),()=>{
    text('SUHAIL HEALTH',98,149,25,'#c6dfd1',750,'Manrope');
    path([[98,174],[275,174]],C.gold,3);
    round(97,305,391,345,29,'#fff','#cfdfd3');logoAt(128,323,329);
    lines(['Guiding every result','to care.'],613,392,87,'#f3f5ec',750,1.18,'Manrope');
    text('One connected screening-to-care journey.',619,650,29,'#c6dfd1');
    pill(`${record.function_count} focused functions`,616,735,304,'#2a5c58','#d7e7da',23);
    pill('Human clinical oversight',943,735,386,'#2a5c58','#d7e7da',23);
    path([[619,850],[1646,850]],'#456e60',3);
    c.beginPath();c.arc(1646,850,8,0,7);c.fillStyle=C.gold;c.fill();
    text('Clear responsibility. Visible next steps. Reviewed source evidence.',619,904,24,'#b2cec1');
  });
};
