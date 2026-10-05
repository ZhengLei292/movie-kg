"""Record real browser interactions with step captions, then encode H.264 MP4."""
import json
import re
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
BUILD=ROOT/'.build/video'

def record():
    BUILD.mkdir(parents=True,exist_ok=True)
    checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1080},record_video_dir=str(BUILD),record_video_size={'width':1600,'height':1080})
        page=context.new_page()
        def caption(text):
            page.evaluate('''text=>{let e=document.getElementById('demo-caption');if(!e){e=document.createElement('div');e.id='demo-caption';document.body.appendChild(e)}e.textContent=text;e.style.cssText='position:fixed;bottom:14px;left:320px;right:30px;padding:14px 24px;background:#173e32;color:white;font:18px system-ui;z-index:999999;border-radius:8px;box-shadow:0 4px 24px #0003;pointer-events:none'}''',text)
        def hold(ms=3500): page.wait_for_timeout(ms)
        def ready(title):
            page.get_by_role('heading',name=title,exact=True).wait_for(timeout=45000)
            page.get_by_text('同分按 movieId 升序。分数表示共享关系数量，不代表预测评分。').wait_for(timeout=30000)
        page.goto('http://127.0.0.1:18501',wait_until='networkidle')
        ready('Toy Story (1995)')
        caption('01 / 系统首页：9,742 部电影，查询、局部图谱与可解释推荐')
        hold(5000)
        search=page.get_by_role('textbox',name='搜索电影')
        search.fill('Toy Story');search.press('Enter')
        page.get_by_role('button',name='Toy Story (1995) · #1',exact=True).wait_for(timeout=30000)
        caption('02 / 部分片名查询：每部电影以 movieId 唯一定位')
        hold()
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,430)');hold(2000)
        caption('03 / 推荐依据：Toy Story 2 共享 5 个类型和 pixar 标签，分数为 6')
        page.screenshot(path=str(OUT/'06-graph-and-reasons.png'))
        hold(5000)
        frame=page.frame_locator('iframe[title="app.moviegraph"]')
        frame.locator('circle[aria-label="Animation"]').click()
        page.get_by_role('button',name='关联下一页').wait_for(timeout=30000)
        caption('04 / 点击 Animation 节点：读取真实类型关系，显示关联电影')
        page.get_by_role('button',name='关联下一页').scroll_into_view_if_needed();hold(4000)
        checks.append('graph_genre_click')
        frame.locator('circle[aria-label="pixar"]').click()
        page.locator('strong').filter(has_text=re.compile('^pixar$')).wait_for(timeout=30000)
        caption('05 / 点击 pixar 标签：浏览具有相同标签的电影')
        hold(4000)
        checks.append('graph_tag_click')
        frame.locator('circle[aria-label="Toy Story 2 (1999)"]').click()
        ready('Toy Story 2 (1999)')
        caption('06 / 点击电影节点：切换图谱中心，重新生成相似推荐')
        hold(4000)
        checks.append('graph_movie_click')
        page.get_by_role('button',name='探索这部电影 ↗').first.click()
        ready('Toy Story (1995)')
        caption('07 / 推荐卡片也能继续探索电影')
        hold(3000)
        search.fill('Emma (1996)');search.press('Enter')
        page.get_by_role('button',name='Emma (1996) · #838',exact=True).wait_for(timeout=30000)
        page.get_by_role('button',name='Emma (1996) · #26958',exact=True).wait_for(timeout=30000)
        caption('08 / 同名电影：Emma 的两条记录具有不同 movieId，独立展示')
        hold(5000)
        page.get_by_role('button',name='Emma (1996) · #26958',exact=True).click()
        ready('Emma (1996)')
        checks.append('duplicate_title_selected_by_id')
        search.fill('xyz-no-such-film');search.press('Enter')
        page.get_by_text('没有找到电影，试试更短的英文名称。').wait_for(timeout=30000)
        caption('09 / 无结果：明确提示，当前电影和推荐仍可继续查看')
        hold(4000)
        page.goto('http://127.0.0.1:18501/?movie=4',wait_until='networkidle')
        ready('Waiting to Exhale (1995)')
        page.get_by_role('tab',name='电影标签').click()
        page.get_by_text('这部电影没有用户标签，推荐将仅根据共同类型计算。').wait_for()
        caption('10 / 无标签：仅使用共同类型推荐，页面正常显示')
        hold(5000)
        checks.append('no_tags_ui')
        page.goto('http://127.0.0.1:18501/?movie=114335',wait_until='networkidle')
        page.get_by_text('没有共享类型或标签的其他电影，暂时无法推荐。').wait_for(timeout=45000)
        caption('11 / 无类型且无标签：没有可用的共同关系，不生成无依据推荐')
        hold(5000)
        checks.append('no_features_ui')
        page.goto('http://127.0.0.1:18501/?movie=1',wait_until='networkidle')
        ready('Toy Story (1995)')
        page.get_by_role('tab',name='数据概览').click()
        caption('12 / 数据概览：真实类型分布；原始 CSV 可重复生成 Neo4j 图谱')
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,330)');hold(5000)
        checks.append('stats_ui')
        assert page.locator('[data-testid="stException"]').count()==0
        video=page.video
        context.close()
        source=video.path()
        browser.close()
    target=OUT/'系统演示.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(source),'-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,capture_output=True)
    (ROOT/'docs/demo_checks.json').write_text(json.dumps({'status':'PASS','checks':checks,'video':str(target.name),'audio':'无配音，含步骤字幕','capture':'真实浏览器连续操作'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(target)

if __name__=='__main__': record()
