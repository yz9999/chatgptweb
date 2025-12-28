from flask import Flask, request, jsonify, send_from_directory
import requests, re, random, string, time, os

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/verify', method=['POST'])
def verify():
    data = request.json
    program_url = data.get('programUrl', '')
    
    # 提取 ID
    v_id_match = re.search(r'verificationId=([a-z0-9]+)', program_url)
    if not v_id_match:
        return jsonify({"error": "无效 ID"}), 400
    
    v_id = v_id_match.group(1)
    
    try:
        # 1. 随机身份
        fname, lname = random.choice([("BRITT", "SLABINSKI"), ("EDWARD", "BYERS"), ("DAVID", "BELLAVIA")])
        
        # 2. 创建邮箱 (Mail.tm)
        domain = requests.get("https://api.mail.tm/domains").json()['hydra:member'][0]['domain']
        email = f"{''.join(random.choices(string.ascii_lowercase, k=10))}@{domain}"
        requests.post("https://api.mail.tm/accounts", json={"address": email, "password": "Password123!"})
        token = requests.post("https://api.mail.tm/token", json={"address": email, "password": "Password123!"}).json()['token']

        # 3. 提交 SheerID
        h = {"User-Agent": "Mozilla/5.0"}
        requests.post(f"https://services.sheerid.com/rest/v2/verification/{v_id}/step/collectMilitaryStatus", json={"status": "VETERAN"}, headers=h)
        requests.post(f"https://services.sheerid.com/rest/v2/verification/{v_id}/step/collectInactiveMilitaryPersonalInfo", json={
            "firstName": fname, "lastName": lname, "email": email,
            "birthDate": "1960-05-15", "organization": {"id": "4070"},
            "dischargeDate": "2025-05-15", "locale": "en-US"
        }, headers=h)

        # 4. 轮询邮件 (Railway 允许长耗时，可以轮询 30 秒)
        confirm_link = None
        for _ in range(15):
            time.sleep(3)
            m_list = requests.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"}).json()
            if m_list.get('hydra:member'):
                msg_id = m_list['hydra:member'][0]['id']
                msg = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers={"Authorization": f"Bearer {token}"}).json()
                match = re.search(r'href="(https://services\.sheerid\.com/verify/[^"]+emailToken=[a-z0-9]+)"', str(msg.get('html')))
                if match:
                    confirm_link = match.group(1).replace("&amp;", "&")
                    break

        if confirm_link:
            return jsonify({"status": "SUCCESS", "link": confirm_link, "email": email})
        return jsonify({"error": "轮询超时"}), 504

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Railway 会通过环境变量提供端口
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
