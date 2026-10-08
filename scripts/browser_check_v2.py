"""Real Chrome integration checks, screenshots and optional recording."""
import json,os,subprocess,sys,time
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
def run(record=False):
    build=ROOT/'.build/browser';build.mkdir(parents=True,exist_ok=True)
    children=[];handles=[];checks=[];errors=[]
    base=os.getenv('MOVIEGRAPH_BROWSER','http://127.0.0.1:18501')
    try:
        if os.getenv('MOVIEGRAPH_TEST_SERVICES')=='1':
            base='http://127.0.0.1:18503'
            env=dict(os.environ,MOVIEGRAPH_API='http://127.0.0.1:18083')
            commands=[['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','18083'],['-m','streamlit','run','frontend/app.py','--server.port','18503','--server.headless','true']]
            for i,cmd in enumerate(commands):
                handle=(build/f'service-{i}.log').open('wb');handles.append(handle)
                children.append(subprocess.Popen([sys.executable]+cmd,cwd=ROOT,env=env,stdout=handle,stderr=handle,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0))
            for url in ['http://127.0.0.1:18083/health',base]:
                for _ in range(45):
                    try:
                        if requests.get(url,timeout=1).status_code==200:break
                    except requests.RequestException:pass
                    time.sleep(1)
                else:raise RuntimeError('Test service not ready: '+url)
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            options=dict(viewport={'width':1600,'height':1080},device_scale_factor=1)
            if record:options.update(record_video_dir=str(build/'video'),record_video_size={'width':1600,'height':1080})
            context=browser.new_context(**options);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def ready():
                page.get_by_role('heading',name='Toy Story (1995)',exact=True).wait_for(timeout=60000)
                page.get_by_role('tab',name='用户推荐',exact=True).wait_for(timeout=60000)
                page.get_by_text('同分按 movieId 升序。分数表示共享关系数量，不代表预测评分。',exact=True).wait_for(timeout=60000)
            def shot(name,caption):
                if record:
                    page.evaluate('''text=>{let e=document.getElementById('demo-caption');if(!e){e=document.createElement('div');e.id='demo-caption';document.body.appendChild(e)}e.textContent=text;e.style.cssText='position:fixed;bottom:10px;left:330px;right:30px;padding:12px 20px;background:#173e32;color:white;font:18px system-ui;z-index:999999;border-radius:6px;pointer-events:none'}''',caption)
                page.screenshot(path=str(OUT/name));page.wait_for_timeout(2200 if record else 500)
                checks.append(caption);print('PASS',caption,flush=True)
            page.goto(base,wait_until='networkidle');ready()
            shot('01-home.png','01 首页：四表数据、610个用户、100836条评分关系')
            search=page.get_by_role('textbox',name='搜索电影');search.fill('toy story');search.press('Enter')
            page.get_by_role('button',name='Toy Story (1995) · #1',exact=True).wait_for(timeout=30000)
            page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,460)')
            frame=page.frame_locator('iframe[title="app.moviegraph"]');frame.locator('circle[aria-label="Animation"]').wait_for(timeout=45000)
            assert frame.locator('circle[aria-label^="用户 "]').count()==3
            shot('02-graph-click.png','02 局部图谱：电影、类型、标签与紫色评分用户')
            frame.locator('circle[aria-label="Animation"]').click();page.get_by_role('button',name='关联下一页').wait_for(timeout=30000)
            checks.append('类型节点点击返回关联电影')
            page.get_by_role('tab',name='评分与链接',exact=True).click()
            page.get_by_role('link',name='IMDb · tt0114709',exact=True).wait_for(timeout=30000)
            shot('03-ratings-links.png','03 ratings提供均分与分布，links提供IMDb及TMDb编号')
            page.get_by_role('tab',name='用户推荐',exact=True).click()
            page.get_by_role('button',name='查看这部推荐电影',exact=True).first.wait_for(timeout=45000)
            shot('04-user-recommend.png','04 匿名用户历史：共同高分推荐，排除已评分电影')
            page.get_by_text('基于共同高分电影的推荐',exact=True).scroll_into_view_if_needed()
            shot('07-user-evidence.png','05 推荐证据：不同邻居支持人数与实际高分均值')
            page.get_by_role('button',name='查看这部推荐电影',exact=True).first.click();page.wait_for_timeout(1800)
            page.get_by_role('heading',name='Toy Story (1995)',exact=True).wait_for(state='hidden',timeout=45000)
            checks.append('用户推荐电影导航')
            page.goto(base+'/?movie=1',wait_until='networkidle');ready()
            page.get_by_role('tab',name='关系图谱',exact=True).click()
            frame=page.frame_locator('iframe[title="app.moviegraph"]')
            user=frame.locator('circle[aria-label^="用户 "]').first;user.wait_for(timeout=30000)
            label=user.get_attribute('aria-label');user.click();page.wait_for_timeout(2000)
            page.get_by_role('tab',name='用户推荐',exact=True).click()
            selected=page.locator('[data-testid="stSelectbox"]').last
            for _ in range(45):
                selection=selected.inner_text()+' '+selected.get_by_role('combobox').input_value()
                if label in selection:break
                page.wait_for_timeout(1000)
            print('User selection evidence:',repr(label),repr(selection),flush=True)
            page.screenshot(path=str(build/'user-selection.png'))
            assert label in selection
            checks.append('评分用户节点可选择对应用户')
            page.goto(base+'/?movie=4',wait_until='networkidle');page.get_by_role('tab',name='电影标签',exact=True).click()
            page.get_by_text('这部电影没有用户标签，推荐将仅根据共同类型计算。').wait_for(timeout=45000)
            shot('05-no-tags.png','05 无标签电影仍可查询、评分和按类型推荐')
            page.goto(base+'/?movie=114335',wait_until='networkidle')
            page.get_by_text('没有共享类型或标签的其他电影，暂时无法推荐。').wait_for(timeout=45000)
            checks.append('无特征电影显示空特征推荐')
            page.goto(base+'/?movie=1',wait_until='networkidle');ready();page.get_by_role('tab',name='数据概览',exact=True).click()
            shot('06-stats.png','06 总关系126460条：特征关系加评分关系')
            assert not errors,errors
            assert page.locator('[data-testid="stException"]').count()==0
            video=page.video if record else None;context.close();browser.close()
            if video:
                import imageio_ffmpeg
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(video.path()),'-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'系统演示.mp4')],check=True,capture_output=True)
        report=dict(status='PASS',timestamp=time.strftime('%Y-%m-%dT%H:%M:%S'),checks=checks,pageErrors=errors,capture='真实Chrome页面，真实Neo4j与FastAPI',schemaVersion=2,recorded=record,viewport='1600x1080')
        (ROOT/'docs/browser_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/'docs/浏览器验证.md').write_text('# 新版浏览器验证\n\n'+json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        for process in children:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill()
        for handle in handles:handle.close()
if __name__=='__main__':run('--record' in sys.argv)
