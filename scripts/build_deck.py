"""Build the self-contained Suhail Health submission deck and its PDF."""
import argparse
from base64 import b64encode
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
SCREENS = ROOT / 'reports' / 'submission-screenshots'


def data_uri(path, media_type):
    return f'data:{media_type};base64,{b64encode(path.read_bytes()).decode()}'


def screenshot(name, alt, style=''):
    source = data_uri(SCREENS / f'{name}.png', 'image/png')
    return f'<img class="screenshot {style}" src="{source}" alt="{alt}">'


def slide(kicker, title, body, style=''):
    return f'''
    <section class="slide {style}">
      <header><p class="kicker">{kicker}</p><h1>{title}</h1></header>
      {body}
    </section>
    '''


def html():
    brand = (ROOT / 'bundle' / 'brand.css').read_text()
    font = data_uri(ROOT / 'apps' / 'web' / 'public' / 'fonts' / 'Manrope.ttf', 'font/ttf')
    logo = data_uri(ROOT / 'bundle' / 'logos' / 'suhail-health-logo-on-dark-640w.png', 'image/png')
    impact = json.loads((ROOT / 'reports' / 'impact' / 'impact-summary.json').read_text())
    usual = impact['arms']['usual_care']['completed_360d'] * 100
    suhail = impact['arms']['suhail']['completed_360d'] * 100
    delta = impact['delta']
    low, high = usual + delta['low_pp'], usual + delta['high_pp']
    run = json.loads((ROOT / 'reports' / 'runs' / '20261120T135507Z-offline' / 'summary.json').read_text())
    passed, selected = run['counts']['task_passed'], run['counts']['selected']
    refused = run['components']['software_suite']['counts']['task_passed']
    sequence = '<span>Result</span><span>Patient informed</span><span>Referral accepted</span><span>Care documented</span>'
    slides = [
        f'''<section class="slide dark cover">
          <p class="kicker">Future Health Digital Innovation Challenge · Population Health</p>
          <div class="cover-content"><img src="{logo}" alt="Suhail Health logo">
            <h1>Guiding every screening<br>result to care.</h1>
            <p>Challenge 05 · Closing the Screening-to-Care Loop · Prototype</p>
          </div><div class="steps">{sequence}</div>
        </section>''',
        slide('The follow-up gap', 'A positive result needs a next step.',
              '''<div class="split centered"><div class="big-stat"><strong>56%</strong><p>completed follow-up colonoscopy within one year in a US cohort.</p></div>
              <div class="callout"><h2>Delay matters</h2><p>Follow-up at 10–12 months was associated with higher odds of colorectal cancer and advanced-stage disease.</p></div></div>
              <footer><a href="https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2800553">Mohl et al., JAMA Network Open, 2023</a> · <a href="https://jamanetwork.com/journals/jama/fullarticle/2620087">Corley et al., JAMA, 2017</a></footer>'''),
        slide('Where results stall', 'Responsibility can get lost at the handoff.',
              '''<div class="diagram three"><div><b>Lab</b><p>Issues the result</p></div><div><b>Sending clinic</b><p>Needs a receiving decision</p></div><div><b>Receiving service</b><p>Must confirm the next step</p></div></div>
              <p class="emphasis">When a decision or visit falls through, someone needs to own recovery.</p>''', 'dark'),
        slide('The solution', 'One accountable record from result to care.',
              f'''<div class="steps">{sequence}</div>
              <div class="diagram three compact"><div><b>Owner</b><p>Every episode</p></div><div><b>Deadline</b><p>Every active step</p></div><div><b>Evidence</b><p>Every completed endpoint</p></div></div>'''),
        slide('Navigator workspace', 'See what needs attention.',
              f'''<div class="panels">{screenshot("worklist", "Navigator worklist with priority and deadlines")}{screenshot("timeline", "Dated case journey with completion times")}</div>
              <div class="paired-caption"><p>Worklist · owners, urgency and due dates</p><p>Timeline · each step and its evidence</p></div>'''),
        slide('Patient workspace', 'Read it. Confirm it. Ask for help.',
              f'''<div class="patient-layout"><div class="patient-copy"><p>Arabic or English secure message.</p><p>A visible care journey and two teach-back questions.</p><p>An uncertain answer creates a navigator task.</p></div>
              {screenshot("patient-arabic", "Arabic mobile patient workspace", "phone")}{screenshot("patient-teachback", "Arabic teach-back form", "phone")}</div>'''),
        slide('Handoff and closure', 'Responsibility changes through a recorded decision.',
              f'''<div class="panels">{screenshot("receiving", "Scoped receiving-provider workspace")}{screenshot("closure", "Clinician closure check with missing requirements")}</div>
              <div class="paired-caption"><p>Provider accepts or gives a reason for rejection.</p><p>Clinician closes only with verified evidence.</p></div>'''),
        slide('Responsible AI', 'People govern clinical decisions.',
              f'''<p class="emphasis">Six bounded agents draft. Trusted urgent signals go straight to staff.</p>
              <div class="diagram two"><div><strong>{passed:,}/{selected:,}</strong><p>Deterministic checks passed</p></div><div><strong>{refused}/{refused}</strong><p>Premature closure attempts refused</p></div></div>
              <footer>Synthetic software evaluation · frozen Product release</footer>''', 'dark'),
        slide('Simulated cohort · declared assumptions', 'More patients complete follow-up.',
              f'''<div class="split centered"><div class="big-stat"><strong>{usual:.0f}% <span>→</span> {suhail:.0f}%</strong><p>By day 360 · range <nobr>{low:.1f}–{high:.1f}%</nobr></p></div>
              <div class="callout"><h2>+{delta['additional_completed_per_10000']:,}</h2><p>Follow-ups per 10,000 actionable results</p></div></div>
              <footer>US cohort calibration and patient-navigation trial effect · simulation, with clinical impact to measure in a pilot</footer>'''),
        slide('Architecture and scale', 'A shared ledger with scoped access.',
              '''<div class="diagram three"><div><b>Intake</b><p>FHIR R4 test feed</p></div><div><b>Workflow</b><p>FastAPI · PostgreSQL · durable worker</p></div><div><b>Role workspaces</b><p>Next.js · synthetic providers</p></div></div>
              <p class="emphasis">Versioned policy, evidence gates and optional drafting behind authorization. Containers support local deployment.</p>'''),
        slide('Path to pilot', 'One network. One pathway. Twelve weeks.',
              '''<div class="steps"><span>Baseline and connect</span><span>Configure and review</span><span>Operate with navigators</span><span>Evaluate</span></div>
              <p class="emphasis">We’re looking for a provider network to measure follow-up, unresolved need, documented closure and patient understanding.</p>''', 'dark'),
    ]
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Suhail Health | Future Health Challenge 05</title>''' + f'''
    <style>
      {brand}
      @font-face {{font-family:Manrope;src:url("{font}") format("truetype");font-weight:200 800}}
      @page {{size:1280px 720px;margin:0}}
      * {{box-sizing:border-box}}
      html,body {{margin:0;background:#dfe9e5;color:#143d3c;font:25px Manrope,Arial,sans-serif;print-color-adjust:exact}}
      .slide {{position:relative;display:flex;flex-direction:column;gap:25px;width:1280px;height:720px;padding:55px 68px;overflow:hidden;background:#f7fbf8;break-after:page}}
      .slide:last-child {{break-after:auto}}
      .slide::before {{content:"";position:absolute;top:0;left:68px;width:100px;height:6px;border-radius:0 0 5px 5px;background:var(--suhail-gold)}}
      .dark {{background:var(--suhail-deep);color:var(--suhail-reversed)}}
      .cover {{justify-content:space-between;background:radial-gradient(circle at 86% 32%,#1e5f5a,transparent 40%),#143d3c}}
      .cover-content img {{width:322px;height:106px;object-fit:contain;object-position:left center;margin-left:-14px}}
      .cover h1 {{font-size:76px;max-width:890px;margin:0 0 18px}}
      .cover-content p {{font-size:22px;color:#c5ded3}}
      h1,h2,p {{margin:0}}
      h1 {{font-size:55px;line-height:1.07;letter-spacing:-.055em}}
      h2 {{font-size:33px;line-height:1.12;letter-spacing:-.025em}}
      .kicker {{font-size:17px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#006568;margin:0 0 13px}}
      .dark .kicker {{color:#eed2a2}}
      .split {{display:grid;grid-template-columns:1.27fr 1fr;align-items:center;gap:45px}}
      .centered {{flex:1;padding-bottom:32px}}
      .big-stat strong {{display:block;white-space:nowrap;font-size:100px;line-height:1.08;color:#006568;letter-spacing:-.08em}}
      .big-stat strong span {{font-size:.65em;color:#98703a;vertical-align:9px}}
      .big-stat p {{max-width:520px;margin-top:16px;font-size:26px}}
      .callout {{padding:34px;border-radius:24px;border:1px solid #c9ded1;background:#eaf5ee}}
      .callout p {{margin-top:13px;line-height:1.45}}
      .callout h2 {{font-size:40px}}
      .diagram {{display:grid;gap:26px;margin:auto 0}}
      .three {{grid-template-columns:repeat(3,1fr)}}
      .two {{grid-template-columns:repeat(2,1fr)}}
      .diagram>div {{min-height:150px;border-radius:20px;padding:27px 26px;background:#eaf5ee;display:grid;align-content:center;gap:8px}}
      .dark .diagram>div {{background:#21504d;border:1px solid #39706a}}
      .diagram b {{font-size:34px;letter-spacing:-.035em}}
      .diagram strong {{font-size:61px;line-height:1;color:#ead09e;letter-spacing:-.06em}}
      .diagram p {{font-size:24px}}
      .compact {{margin-top:12px}}
      .steps {{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0 0}}
      .steps span {{display:flex;align-items:center;justify-content:center;text-align:center;min-height:76px;padding:10px 14px;border-radius:12px;background:#eaf5ee;border-bottom:4px solid var(--suhail-gold);font-size:20px;font-weight:800}}
      .dark .steps span {{background:#23615b}}
      .emphasis {{font-size:27px;line-height:1.45;max-width:900px}}
      .panels {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}}
      .screenshot {{width:100%;aspect-ratio:1440/950;display:block;object-fit:contain;border-radius:14px;border:1px solid #b6d1c5;box-shadow:0 7px 24px #143d3c12}}
      .paired-caption {{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
      .paired-caption p {{font-size:19px;font-weight:700}}
      .patient-layout {{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:24px;align-items:start}}
      .patient-copy {{display:flex;flex-direction:column;gap:20px;padding:44px 15px 0 0}}
      .patient-copy p {{line-height:1.32}}
      .screenshot.phone {{height:425px;width:auto;max-width:100%;aspect-ratio:390/844;background:white}}
      footer {{margin-top:auto;font-size:16px;color:#4a675e}}
      .dark footer {{color:#bdd9d0}}
      a {{color:inherit;text-underline-offset:3px}}
    </style></head><body>{''.join(slides)}</body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-dir', type=Path)
    args = parser.parse_args()
    build = DOCS / 'deck'
    build.mkdir(parents=True, exist_ok=True)
    source = build / 'deck.html'
    source.write_text(html(), encoding='utf-8')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.goto(source.as_uri(), wait_until='load')
        page.evaluate('document.fonts.ready')
        assert page.locator('.slide').count() == 11
        assert page.locator('img').evaluate_all('(images) => images.every(image => image.complete && image.naturalWidth)')
        overflows = page.locator('.slide').evaluate_all(
            '(slides) => slides.flatMap((slide, i) => slide.scrollHeight > 721 || slide.scrollWidth > 1281 ? [i + 1] : [])'
        )
        if overflows:
            raise RuntimeError(f'Overflowing slides {overflows}')
        page.pdf(path=str(DOCS / 'Suhail_Health_Deck.pdf'), print_background=True, prefer_css_page_size=True)
        if args.preview_dir:
            args.preview_dir.mkdir(parents=True, exist_ok=True)
            for index in (0, 4, 5, 8, 10):
                page.locator('.slide').nth(index).screenshot(path=str(args.preview_dir / f'slide-{index+1:02}.png'))
        browser.close()
    print('Built eleven slides at docs/Suhail_Health_Deck.pdf')


if __name__ == '__main__':
    main()
