import base64
import time
import requests
import json
import os
import re
import pandas as pd
import warnings
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types
from dotenv import load_dotenv
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from jinja2 import Template
from datetime import datetime

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# ==========================================
# 1. SETUP ENV & DIRECTORIES
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "outputs", "POC_Tier1")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# 2. TARGETS & KATE/THOMAS SEO MATRIX
# ==========================================
POC_TARGETS = [
    #{"name": "Southern Cross Metal Recyclers", "url": "https://www.southerncrossmetalrecyclers.com.au/"},
    #{"name": "Vie Capital", "url": "https://www.viecapital.com.au/"},
    #{"name": "WiZDOM", "url": "https://wizdom.com.au/"},
    #{"name": "Axis Jiu Jitsu Melbourne", "url": "https://axisjiujitsumelbourne.com.au/"},
    #{"name": "Corner Hotel", "url": "https://cornerhotel.com/"},
    #{"name": "Orthotech", "url": "https://orthotech.com.au/"},
    #{"name": "Cythera", "url": "https://www.cythera.com.au/"},
    #{"name": "William Buck", "url": "https://williambuck.com/"},
    #{"name": "Think in Colour", "url": "https://www.think-in-colour.com.au/"},
    #{"name": "Scott Pickett Group", "url": "https://www.scottpickettgroup.com.au/"},
    #{"name": "Salter Brothers", "url": "https://salterbrothers.com.au/"},
    #{"name": "Future Leadership", "url": "https://futureleadership.com.au/"},
    #{"name": "Woomargama Station", "url": "https://woomargamastation.com.au/"},
    {"name": "Deliberate Practice", "url": "https://www.deliberatepractice.com.au/"}
]

SEO_AEO_CATEGORIES = [
    "technical_seo_foundations", 
    "on_page_meta_hierarchy", 
    "schema_markup_presence", 
    "aeo_content_structure", 
    "faq_quality_and_formatting", 
    "ai_visibility_signals"
]

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def scrape_seo_data(url):
    """Scrape technical SEO, Meta Tags, JSON-LD Schema, and perform SHALLOW SPIDER DOM Scan for AI Context."""
    print(f"   -> [Scraper] Extracting SEO/AEO DOM data for {url}...")
    data = {
        "title": "Not Found",
        "meta_description": "Not Found",
        "h1_tags": [],
        "has_schema": False,
        "schema_types": [],
        "has_faq_schema": False,
        "has_faq_visual": False,
        "faq_location": "homepage" 
    }
    
    try:
        # Pura-pura jadi browser Chrome versi terbaru
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        response = requests.get(url, headers=headers, timeout=20)
        
        # 🚨 BYPASS 403 FORBIDDEN WAF (Cloudflare/Imperva) 🚨
        if response.status_code in [403, 406, 503]:
            print(f"   -> [WAF BLOCKED] {response.status_code} detected. Switching to Stealth Mode to bypass...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
                context = browser.new_context(user_agent=headers['User-Agent'])
                page = context.new_page()
                
                # 🚨 NATIVE STEALTH INJECTION 🚨
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                page.add_init_script("window.navigator.chrome = { runtime: {} };")
                page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
                
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                html_content = page.content()
                browser.close()
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"   -> [BYPASS SUCCESS] Successfully extracted DOM via Stealth Playwright.")
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Base Meta & Schema Check on Homepage
        if soup.title and soup.title.string:
            data["title"] = soup.title.string.strip()
            
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            data["meta_description"] = meta_desc["content"].strip()
            
        data["h1_tags"] = [h1.get_text(strip=True) for h1 in soup.find_all('h1')][:3]
        
        schemas = soup.find_all("script", type="application/ld+json")
        if schemas:
            data["has_schema"] = True
            for schema in schemas:
                try:
                    if not schema.string: continue
                    json_content = json.loads(schema.string)
                    items_to_check = json_content if isinstance(json_content, list) else [json_content]
                    for item in items_to_check:
                        if isinstance(item, dict):
                            data["schema_types"].append(item.get('@type', 'Unknown'))
                            if item.get('@type') == 'FAQPage': data["has_faq_schema"] = True
                except:
                    pass
                    
        # 2. Visual FAQ Check on Homepage 
        text_content = soup.get_text().lower()
        if "frequently asked questions" in text_content or re.search(r'\bfaq\bs?', text_content):
            data["has_faq_visual"] = True
                
        if not data["has_faq_visual"]:
            if soup.find(class_=re.compile(r'\bfaq\b', re.I)) or soup.find(id=re.compile(r'\bfaq\b', re.I)):
                data["has_faq_visual"] = True

        # 3. KATE'S SHALLOW SPIDER (Deep Crawl Backup)
        if not data["has_faq_schema"] or not data["has_faq_visual"]:
            print(f"   -> [Spider] FAQ not fully detected on homepage. Initiating Shallow Crawl...")
            subpages_to_check = []
            domain_netloc = urlparse(url).netloc
            
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').lower()
                if any(k in href for k in ['faq', 'resource', 'service', 'support', 'help']):
                    full_url = urljoin(url, a['href'])
                    if urlparse(full_url).netloc == domain_netloc:
                        if full_url not in subpages_to_check and full_url != url:
                            subpages_to_check.append(full_url)
                if len(subpages_to_check) >= 3: 
                    break
            
            for sub_url in subpages_to_check:
                if data["has_faq_visual"] and data["has_faq_schema"]: break
                try:
                    sub_res = requests.get(sub_url, headers=headers, timeout=10)
                    sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                    path_name = urlparse(sub_url).path.strip('/') or 'subpage'
                    
                    if not data["has_faq_visual"]:
                        sub_text = sub_soup.get_text().lower()
                        if "frequently asked questions" in sub_text or re.search(r'\bfaq\bs?', sub_text):
                            data["has_faq_visual"], data["faq_location"] = True, f"/{path_name}"
                            
                    if not data["has_faq_schema"]:
                        sub_schemas = sub_soup.find_all("script", type="application/ld+json")
                        for schema in sub_schemas:
                            if schema.string and 'FAQPage' in schema.string:
                                data["has_faq_schema"], data["faq_location"] = True, f"/{path_name}"
                except:
                    continue
            
    except Exception as e:
        print(f"   -> [WARNING] SEO Scrape failed: {e}")
        
    return data

def take_dual_screenshots(url, target_name):
    print(f"   -> [Playwright] Generating Hero & Content screenshots for {target_name}...")
    safe_name = target_name.replace(" ", "_")
    hero_path = os.path.join(OUTPUT_DIR, f"{safe_name}_hero.png")
    trust_path = os.path.join(OUTPUT_DIR, f"{safe_name}_content.png")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        # 🚨 NATIVE STEALTH INJECTION SAAT SCREENSHOT 🚨
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.add_init_script("window.navigator.chrome = { runtime: {} };")
        page.add_init_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]})")
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000) 
            
            page.screenshot(path=hero_path, full_page=False)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(3000) 
            page.screenshot(path=trust_path, full_page=False)
            
        except Exception as e:
            print(f"   -> [ERROR] Screenshot failed for {url}: {e}")
        finally:
            browser.close()
            
    return hero_path, trust_path

def check_google_ranking(keyword, domain):
    print(f"   -> [Rank Tracker] Checking Google AU for: '{keyword}'")
    clean_domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
    clean_domain = clean_domain.split('/')[0]
    
    url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&gl=au&hl=en-AU&num=20"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-AU,en;q=0.9'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        search_results = soup.find_all('div', class_='g')
        rank = 1
        for result in search_results:
            link_element = result.find('a', href=True)
            if link_element and 'url?q=' not in link_element['href']: 
                href = link_element['href']
                if clean_domain in href:
                    if rank == 1: return "#1 (Winning — replicate this approach)"
                    elif rank <= 3: return f"#{rank} (Top 3 — High visibility)"
                    elif rank <= 10: return f"#{rank} (Page 1 — Good, but push for top 3)"
                    else: return f"#{rank} (Page 2 — Needs work to drive traffic)"
                rank += 1
                if rank > 20: break
        return "Not in top 20 (Missed opportunity)"
    except Exception as e:
        print(f"   -> [WARNING] Google Scrape failed for {keyword}: {e}")
        return "Check failed"

def generate_seo_aeo_audit(scrape_data, site_img_path, target_name, client):
    """Execute Gemini 2.5 Vision AI with Kate's Strict UI/UX Matrix."""
    print(f"   -> [AI] Executing Gemini 2.5 Vision AI (SEO & AEO Engine)...")
    try:
        site_snapshot = client.files.upload(file=site_img_path)
        payload = [site_snapshot]
        
        prompt = f"""
        You are an elite SEO & AEO Technical Consultant at BlueRock Digital. 
        Analyze the website screenshot for "{target_name}" and the DOM data:
        - Meta Title: {scrape_data['title']}
        - Meta Description: {scrape_data['meta_description']}
        - H1 Tags: {scrape_data['h1_tags']}
        - JSON-LD Schema: {scrape_data['has_schema']}
        - FAQ Schema: {scrape_data['has_faq_schema']}
        - Visual FAQ Detected: {scrape_data['has_faq_visual']}
        - FAQ Location: {scrape_data['faq_location']}

        CRITICAL AUDIT RULES (STRICTLY ENFORCE):
        1. LANGUAGE: You MUST use Australian English spelling (e.g., 'organisation', 'optimise', 'centre').
        2. TITLES: Use sentence case for all titles (e.g., 'Website health' instead of 'Website Health').
        3. SCORING: 0="High", 1="Medium", 2="Good".
        4. BUSINESS IMPACT: Provide a `business_impact` explaining the consequence in plain English.
        5. EFFORT ESTIMATION: Assign `effort_label`: "Quick win", "Light lift", "Moderate build", or "Strategic project". DO NOT USE EMOJIS.
        
        SPECIFIC CATEGORY INSTRUCTIONS:
        - faq_quality_and_formatting: 
          * IF Visual is True AND Schema is False: Severity High. 
            Finding: "FAQ content exists on the {scrape_data['faq_location']} page but lacks FAQPage schema markup. Without this structured data, AI answer engines cannot reliably identify it as Q&A content." 
            Recommendation: "Inject FAQPage JSON-LD into the <head> of the page. No new section needed - schema-only fix."
        
        OUTPUT SCHEMA INSTRUCTION (JSON ONLY):
        You MUST return EXACTLY 6 objects in the 'audits' array. 
        The 'category' value of each object MUST be EXACTLY one of these strings:
        1. "technical_seo_foundations"
        2. "on_page_meta_hierarchy"
        3. "schema_markup_presence"
        4. "aeo_content_structure"
        5. "faq_quality_and_formatting"
        6. "ai_visibility_signals"

        Format:
        {{
            "target_keywords": ["keyword 1", "keyword 2", "keyword 3"],
            "audits": [
                {{
                  "category": "technical_seo_foundations", 
                  "severity": "Good", 
                  "title": "Your sentence case title",
                  "finding": "...",
                  "business_impact": "...",
                  "recommendation": "...",
                  "effort_label": "Quick win"
                }}
            ]
        }}
        """
        payload.append(prompt)
        
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=payload,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", 
                        temperature=0.2
                    ),
                )
                
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:-3].strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:-3].strip()
                    
                return json.loads(raw_text)
                
            except Exception as e:
                if '503' in str(e) or '429' in str(e):
                    wait_time = 10 * (2 ** attempt)
                    print(f"   -> [WARNING] API Overloaded. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"   -> [ERROR] Unhandled AI exception: {e}")
                    return None
        return None
        
    except Exception as e:
        print(f"   -> [ERROR] AI Processing failed: {e}")
        return None

def build_formatted_excel(df, output_path):
    print("   -> [Formatter] Generating Premium Excel File...")
    
    df_excel = df.copy()
    df_excel['category'] = df_excel['category'].str.replace('_', ' ').str.title()
    
    if 'rankings_data' in df_excel.columns:
        df_excel['Google Rankings'] = df_excel['rankings_data'].apply(
            lambda r: "\n".join([f"{item['keyword']}: {item['rank']}" for item in r]) if isinstance(r, list) else ""
        )
        df_excel = df_excel.drop(columns=['rankings_data'])
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Month 1 - SEO AEO')
        ws = writer.sheets['Month 1 - SEO AEO']

        header_fill = PatternFill(start_color='1B263B', end_color='1B263B', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        high_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        med_fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')
        low_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        for col_num in range(1, len(df_excel.columns) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        for row_num in range(2, len(df_excel) + 2):
            severity_val = ws.cell(row=row_num, column=3).value
            for col_num in range(1, len(df_excel.columns) + 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.border = thin_border
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                
                if col_num == 3:
                    if severity_val == 'High': cell.fill = high_fill
                    elif severity_val == 'Medium': cell.fill = med_fill
                    elif severity_val == 'Low': cell.fill = low_fill

        column_widths = [20, 25, 12, 25, 45, 45, 45, 18, 15, 30]
        for i, width in enumerate(column_widths):
            if i < len(df_excel.columns):
                ws.column_dimensions[get_column_letter(i + 1)].width = width

def generate_automated_pdf(client_name, url, hero_path, trust_path, analysis, client_rankings, output_dir):
    print(f"   -> [PDF Engine] Injecting data into HTML and rendering PDF for {client_name}...")

    def image_to_base64(img_path):
        with open(img_path, "rb") as image_file:
            return "data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8')

    # 1. Bikin dictionary dari hasil AI dengan aman
    findings_dict = {}
    if analysis:
        findings_dict = {item.get('category', 'unknown'): item for item in analysis if isinstance(item, dict)}
    
    # 2. 🚨 SISTEM ANTI-CRASH BULLETPROOF 🚨
    for cat in SEO_AEO_CATEGORIES:
        if cat not in findings_dict:
            findings_dict[cat] = {
                "category": cat,
                "severity": "High",
                "title": "Audit blocked by security",
                "finding": "The site's security firewall (WAF) prevented the engine from extracting this specific DOM element.",
                "business_impact": "Overly strict firewalls can inadvertently block legitimate AI crawlers like ChatGPT from reading your site.",
                "recommendation": "Review firewall rules to ensure emerging AI crawlers are whitelisted.",
                "effort_label": "Light lift" # <--- EMOJI DIHAPUS DI SINI
            }

    # 3. Kalkulasi murni
    count_critical = sum(1 for x in findings_dict.values() if x.get('severity') == 'High')
    count_important = sum(1 for x in findings_dict.values() if x.get('severity') == 'Medium')
    count_low = sum(1 for x in findings_dict.values() if x.get('severity') in ['Low', 'Good'])
    
    total_deductions = (count_critical * 2) + (count_important * 1) + (count_low * 0.5)
    raw_score = max(0, 10 - total_deductions)
    audit_score = int(raw_score) if float(raw_score).is_integer() else raw_score

    if audit_score >= 9:
        score_label = "🔵 Best in Class"
        monetization_text = "You're competing at the top. Maintenance, monitoring and content depth are the priorities from here."
    elif audit_score >= 7:
        score_label = "🟢 Strong Foundation"
        monetization_text = "Your site is well-structured for search and AI. Focus shifts from fixing to growing — capturing more keywords and AI mentions."
    elif audit_score >= 5:
        score_label = "🟡 Functional but Underperforming"
        monetization_text = "The basics are in place. Targeted improvements will move you from 'found sometimes' to 'consistently recommended'."
    elif audit_score >= 3:
        score_label = "🟠 Significant Gaps"
        monetization_text = "Some foundations exist but key signals are missing. You're appearing in some searches but losing clicks to better-optimised competitors."
    else:
        score_label = "🔴 Needs Immediate Attention"
        monetization_text = "Your website is largely invisible to Google and AI tools. Customers searching for your services are finding competitors instead."

    # 4. TRANSLATOR STATUS UNTUK KATE WIGGINS (BARU)
    for key, item in findings_dict.items():
        sev = item.get('severity', '')
        if sev == 'High':
            item['display_status'] = 'Critical issue'
        elif sev == 'Medium':
            item['display_status'] = 'Needs attention'
        elif sev in ['Low', 'Good']:
            item['display_status'] = 'Healthy status'
        else:
            item['display_status'] = sev

    data = {
        "client_name": client_name,
        "count_critical": count_critical,
        "count_important": count_important,
        "count_low": count_low,
        "client_url": url.replace("https://", "").replace("http://", "").strip("/"),
        "report_date": datetime.now().strftime("%d %B %Y"),
        "audit_score": audit_score,
        "score_label": score_label,
        "monetization_text": monetization_text,
        "hero_img_path": image_to_base64(hero_path),
        "trust_img_path": image_to_base64(trust_path),
        "findings": findings_dict,
        "google_rankings": client_rankings 
    }

    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, "report_template.html")
    if not os.path.exists(template_path):
        print("   -> [ERROR] report_template.html not found! Ensure it is in the BASE_DIR.")
        return None

    with open(template_path, 'r', encoding='utf-8') as f:
        template_str = f.read()

    template = Template(template_str)
    rendered_html = template.render(**data)

    safe_name = client_name.replace(" ", "_")
    pdf_path = os.path.join(output_dir, f"{safe_name}_SEO_AEO_Review.pdf")
    
    html_path = os.path.join(output_dir, f"{safe_name}_Interactive_SEO_Report.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(rendered_html)
    print(f"   -> [HTML] Interactive file saved: {html_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html, wait_until="load")
        page.pdf(
            path=pdf_path,
            width="1920px",
            height="1080px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()

    return pdf_path

# ==========================================
# 4. EXECUTION FLOW
# ==========================================
# Tambahkan ini di bagian paling bawah auditor.py lo
def run_single_audit(url, company_name):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    scrape_data = scrape_seo_data(url)
    hero_path, trust_path = take_dual_screenshots(url, company_name)
    
    if not os.path.exists(hero_path) or not os.path.exists(trust_path):
        return {"error": "Failed to capture screenshots"}
        
    ai_response = generate_seo_aeo_audit(scrape_data, hero_path, company_name, client)
    
    if not ai_response or "audits" not in ai_response:
        return {"error": "AI failed to process"}

    ranking_results = []
    for kw in ai_response.get("target_keywords", []):
        rank = check_google_ranking(kw, url)
        ranking_results.append({"keyword": kw, "rank": rank})
        
    for item in ai_response["audits"]:
        item["client_name"] = company_name
        item["rankings_data"] = ranking_results
        
    df_results = pd.DataFrame(ai_response["audits"])
    cols = ['client_name', 'category', 'severity', 'title', 'finding', 'business_impact', 'recommendation', 'effort_label', 'rankings_data']
    available_cols = [c for c in cols if c in df_results.columns]
    df_results = df_results[available_cols]
    df_results['QA_Status'] = 'Pending Review'
    
    safe_name = company_name.replace(" ", "_")
    csv_output = os.path.join(OUTPUT_DIR, f"{safe_name}_Raw.csv")
    excel_output = os.path.join(OUTPUT_DIR, f"{safe_name}_Formatted.xlsx")
    
    df_results.to_csv(csv_output, index=False)
    build_formatted_excel(df_results, excel_output)
    
    pdf_path = generate_automated_pdf(company_name, url, hero_path, trust_path, ai_response["audits"], ranking_results, OUTPUT_DIR)
    html_path = os.path.join(OUTPUT_DIR, f"{safe_name}_Interactive_SEO_Report.html")
    
    return {
        "pdf_url": f"/outputs/POC_Tier1/{os.path.basename(pdf_path)}",
        "excel_url": f"/outputs/POC_Tier1/{os.path.basename(excel_output)}",
        "html_url": f"/outputs/POC_Tier1/{os.path.basename(html_path)}"
    }