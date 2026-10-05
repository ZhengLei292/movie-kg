"""Browser smoke and interaction tests, screenshots, and optional video recording."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'

def run():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1050},device_scale_factor=1)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:18501',wait_until='networkidle')
        page.get_by_role('heading',name='Toy Story (1995)',exact=True).wait_for(timeout=60000)
        page.get_by_text('同分按 movieId 升序。分数表示共享关系数量，不代表预测评分。').wait_for(timeout=30000)
        page.screenshot(path=str(OUT/'01-home.png'),full_page=True)
        frame=page.frame_locator('iframe[title="app.moviegraph"]')
        frame.locator('circle').first.wait_for(timeout=10000)
        frame.locator('circle[aria-label="Animation"]').click()
        page.wait_for_timeout(1200)
        page.get_by_role('button',name='关联下一页').wait_for(timeout=30000)
        page.screenshot(path=str(OUT/'02-graph-click.png'),full_page=True)
        page.get_by_role('button',name='探索这部电影 ↗').first.click()
        page.wait_for_timeout(1500)
        page.get_by_role('heading',name='Toy Story 2 (1999)',exact=True).wait_for(timeout=30000)
        page.screenshot(path=str(OUT/'03-recommendation.png'),full_page=True)
        search=page.get_by_role('textbox',name='搜索电影')
        search.fill('qzxv_no_such_movie_991'); search.press('Enter')
        page.get_by_text('没有找到电影，试试更短的英文名称。').wait_for()
        search.fill('Toy'); search.press('Enter')
        page.wait_for_timeout(1200)
        search.fill('Emma (1996)');search.press('Enter')
        page.get_by_role('button',name='Emma (1996) · #838',exact=True).wait_for(timeout=30000)
        page.get_by_role('button',name='Emma (1996) · #26958',exact=True).wait_for(timeout=30000)
        page.screenshot(path=str(OUT/'04-search.png'),full_page=True)
        page.goto('http://127.0.0.1:18501/?movie=2',wait_until='networkidle')
        page.get_by_role('heading',name='Jumanji (1995)',exact=True).wait_for(timeout=30000)
        page.get_by_role('tab',name='数据概览').click()
        page.wait_for_timeout(1500)
        assert page.locator('[data-testid="stException"]').count()==0
        page.screenshot(path=str(OUT/'05-stats.png'),full_page=True)
        assert not errors,errors
        (ROOT/'docs/browser_results.json').write_text(json.dumps({'status':'PASS','pageErrors':errors,
            'checks':['home renders','graph genre click','recommendation navigation','empty search','search query','stats tab'],
            'viewport':'1600x1050'},ensure_ascii=False,indent=2),encoding='utf-8')
        context.close();browser.close()

if __name__=='__main__': run()
