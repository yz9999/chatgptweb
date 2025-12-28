from http.server import BaseHTTPRequestHandler
import json
import requests
import re
import random
import string
import time

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        req_body = json.loads(post_data)
        program_url = req_body.get('programUrl', '')

        # 1. 提取 ID
        v_id_match = re.search(r'verificationId=([a-z0-9]+)', program_url)
        if not v_id_match:
            return self.send_err("链接中未找到验证 ID")
        
        v_id = v_id_match.group(1)

        try:
            # 2. 随机身份
            fname, lname = random.choice([
                ("BRITT", "SLABINSKI"), ("EDWARD", "BYERS"), ("DAVID", "BELLAVIA"),
                ("FLORENT", "GROBERG"), ("CLINTON", "ROMESHA")
            ])
            
            # 3. 创建 Mail.tm 邮箱
            domain = requests.get("https://api.mail.tm/domains").json()['hydra:member'][0]['domain']
            acc_name = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{acc_name}@{domain}"
            password = "Password123!"
            
            requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password})
            token_resp = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}).json()
            token = token_resp.get('token')

            # 4. SheerID 模拟提交
            h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            # Step 1: Status
            requests.post(f"https://services.sheerid.com/rest/v2/verification/{v_id}/step/collectMilitaryStatus", 
                          json={"status": "VETERAN"}, headers=h)
            # Step 2: Info
            requests.post(f"https://services.sheerid.com/rest/v2/verification/{v_id}/step/collectInactiveMilitaryPersonalInfo", 
                          json={
                              "firstName": fname, "lastName": lname, "email": email,
                              "birthDate": "1960-05-15", "organization": {"id": "4070"},
                              "dischargeDate": "2025-05-15", "locale": "en-US"
                          }, headers=h)

            # 5. 轮询邮件 (Vercel 免费版函数限制 10 秒运行时间，所以只能快速轮询)
            confirm_link = None
            for _ in range(5): 
                time.sleep(1.5)
                m_list = requests.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"}).json()
                if m_list.get('hydra:member'):
                    msg_id = m_list['hydra:member'][0]['id']
                    msg_detail = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers={"Authorization": f"Bearer {token}"}).json()
                    html_content = str(msg_detail.get('html'))
                    match = re.search(r'href="(https://services\.sheerid\.com/verify/[^"]+emailToken=[a-z0-9]+)"', html_content)
                    if match:
                        confirm_link = match.group(1).replace("&amp;", "&")
                        break

            if confirm_link:
                self.send_ok({"status": "SUCCESS", "link": confirm_link, "email": email, "name": f"{fname} {lname}"})
            else:
                self.send_ok({"status": "TIMEOUT", "error": "邮件未在10秒内到达，请刷新重试。"})

        except Exception as e:
            self.send_err(str(e))

    def send_ok(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def send_err(self, msg):
        self.send_response(400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())
