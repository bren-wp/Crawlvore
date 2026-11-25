from pathlib import Path
from playwright.sync_api import sync_playwright
import json, os, sys, tempfile
root=Path(__file__).resolve().parents[1]; out=root/'branding'; out.mkdir(exist_ok=True); views=['overview','directory','registry','jobs','data','analytics','settings']; errors=[]; results=[]
html=(root/'static/index.html').read_text(encoding='utf-8'); css=(root/'static/style.css').read_text(encoding='utf-8'); js=(root/'static/app.js').read_text(encoding='utf-8'); locale_js=(root/'static/locale.js').read_text(encoding='utf-8'); html=html.replace('<link rel="stylesheet" href="/style.css">','').replace('<script defer src="/app.js"></script>','').replace('<script defer src="/locale.js"></script>','').replace('<link rel="icon" href="/logo.svg" type="image/svg+xml">','')
sys.path.insert(0,str(root))
from core import Store
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'test.sqlite3'); store.seed(root/'tvrtk_output.csv'); stats=store.stats(); companies=store.query(limit=5); detail=store.detail(companies["rows"][0]["id"]); providers=[dict(x,label=x['provider']) for x in store.providers()]
fixtures={'/api/stats':stats,'/api/companies':companies,'/api/cities':['Zagreb','Rijeka'],'/api/providers':providers,'/api/projects':[],'/api/registry':{'runs':[{'snapshot':'22','complete':1},{'snapshot':'21','complete':1}],'categories':[],'configured':False},'/api/jobs':{'jobs':[],'schedule':{'enabled':0,'hour':3}},'/api/status':{'status':'idle','page':0,'last':0,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}}
fixtures['/api/company/'+str(companies['rows'][0]['id'])]=detail
fixtures['/api/history/'+str(companies['rows'][0]['id'])]=[]
fixtures['/api/analytics']={'days':[]}
fixtures['/api/recovery']={'backups':[],'recovered':[],'active':'primary','selected':'primary'}
fixtures['/api/recovery/integrity']={'running':False,'search':'ok','workspaces':[{'id':'primary','status':'ok'}]}
fixtures['/api/registry/diff']={'before':'21','after':'22','categories':[{'category':'subjekti','comparable':True,'added':4,'removed':2,'affected_subjects':3}]}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.getenv('CRAWLVORA_TEST_CHROMIUM') or None,headless=True)
 for lang in ['hr','en']:
  page=b.new_page(viewport={'width':1440,'height':900}); page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html.replace('__LANGUAGE__',lang)); page.add_style_tag(content=css)
  page.evaluate('(data)=>{window.fetch=async (path)=>({ok:true,json:async()=>data[path.split("?")[0]]??{}})}',fixtures)
  page.add_script_tag(content=locale_js); page.add_script_tag(content=js)
  page.locator('#preview-rows tr .textbtn').first.wait_for(timeout=10000)
  assert page.locator('#preview-rows tr .textbtn').count()>0
  assert page.locator('html').get_attribute('lang')==lang
  assert page.locator('#overview h1').inner_text()==('Overview' if lang=='en' else 'Pregled imenika')
  assert page.locator('[data-view="directory"]').inner_text().endswith('Business Directory' if lang=='en' else 'Poslovni imenik')
  assert page.locator('#top-export').inner_text()==('⇄ Import / Export' if lang=='en' else '⇄ Uvoz i izvoz')
  prefix='en-' if lang=='en' else ''
  for theme in ['dark','light']:
   page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
   for width,height in [(1440,900),(390,844)]:
    page.set_viewport_size({'width':width,'height':height})
    for view in views:
     page.evaluate('(v)=>go(v)',view); page.wait_for_timeout(120); assert page.locator('#'+view).is_visible()
     if view=='directory':
      page.locator('#company-rows tr .textbtn').first.wait_for(timeout=10000)
     if view=='registry':
      page.locator('#reg-categories tr').first.wait_for(timeout=10000)
      page.locator('#diff-run').click(); page.wait_for_timeout(100); assert page.locator('#diff-rows tr').count()==1
     if view=='jobs':
      page.locator('#job-rows tr').first.wait_for(timeout=10000)
     if view=='analytics':
      page.locator('#analytics-metrics .metric').first.wait_for(timeout=10000)
     if view=='settings':
      page.locator('#settings-count').wait_for(timeout=10000)
     assert not page.locator('#toast').is_visible(), page.locator('#toast').text_content()
     result=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})'); results.append((lang,theme,width,view,result['scroll'])); assert result['scroll']<=width,(lang,theme,width,view,result)
     page.evaluate('window.scrollTo(0,0)'); page.screenshot(path=str(out/(f'{prefix}{view}-{theme}-{width}-fixture.png')),full_page=True)
    page.evaluate('(id)=>detail(id)',companies['rows'][0]['id']); page.wait_for_timeout(120); assert page.locator('#detail').is_visible()
    box=page.locator('#detail').bounding_box(); assert box['width']<=width+1
    page.screenshot(path=str(out/f'{prefix}detail-{theme}-{width}-fixture.png')); page.locator('[data-profile-tab="history"]').click(); assert page.locator('.history-block').is_visible() and not page.locator('.profile-property').first.is_visible(); page.locator('[data-profile-tab="sources"]').click(); assert page.locator('.profile-sources').is_visible() and not page.locator('.history-block').is_visible(); page.locator('#close-detail').click(); assert not page.locator('#detail').is_visible(); results.append((lang,theme,width,'detail',box['width']))
  page.close()
 b.close()
print('errors',errors,'layout',results)
assert not errors
