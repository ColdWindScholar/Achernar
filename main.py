import os
import random
import threading
import time

import yaml
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, Response

import requests
import platform

from playwright.sync_api import sync_playwright
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# 加载账户信息

with open('config.yaml', 'r', encoding='utf-8') as f:
    data = yaml.load(f.read(), Loader=yaml.FullLoader)

app = Flask(__name__)

# 全局变量，存储最新的隧道地址
tunnel_url = []
global url_index
url_index = 0


def start_instance(email, password):
    try:
        # 使用 Playwright 启动浏览器
        with sync_playwright() as p:
            launch_args = {
                "headless": data["headless"],  # 替换为你的 data["headless"]
                "args": ["--no-sandbox", "--disable-dev-shm-usage"]
            }
            proxy = data['proxy']
            if proxy != None and proxy != '' and proxy != "":  # 如果 proxy 不为空
                launch_args["proxy"] = {
                    "server": proxy
                }
                print(f"使用代理 {proxy}")

            browser = p.chromium.launch(**launch_args)
            context = browser.new_context()

            # 打开新的页面
            page = context.new_page()

            # 访问登录页面
            page.goto("https://www.kaggle.com/account/login", timeout=900000)
            print(f"尝试登录账户 {email}")

            # 等待并填写登录信息
            login_button_xpath = '//*[@id="site-content"]/div[2]/div/div/div[1]/form/div/div/div[1]/button[2]'
            page.click(login_button_xpath)
            page.fill('//*[@id=":r0:"]', email)  # 填写邮箱
            page.fill('//*[@id=":r1:"]', password)  # 填写密码
            page.click('//*[@id="site-content"]/div[2]/div/div/div[1]/form/div/div[4]/button[2]')  # 提交登录表单

            print("登录信息已提交。")
            time.sleep(8)  # 等待登录完成

            # 访问目标页面
            page.goto(data["shared_notebook"], timeout=900000)  # 替换成目标页面的URL
            print("尝试运行项目")

            # 尝试运行项目
            time.sleep(10)  # 等待项目加载完成
            if find_and_click(page, "Copy & Edit"):
                print("kaggle要求二次点击，点击Edit in Kaggle Notebooks")
                if not find_and_click(page, "Edit in Kaggle Notebooks"):
                    twice_buttons = ["/html/body/div[3]/div[3]/li[1]/div"]
                    for twi in twice_buttons:
                        try:
                            page.wait_for_selector(twi, state="visible",
                                                   timeout=30000)  # 使用wait_for_selector替换is_visable
                            page.click(twi)
                            print("已选择kaggle")
                            break
                        except Exception as e:
                            print(f"尝试点击 {twi} 失败: 尝试使用其他xpath路径定位")
            else:
                if find_and_click(page, "Edit My Copy"):
                    pass
                else:
                    page.wait_for_selector('//*[@id="site-content"]/div[2]/div/div/div[2]/div[1]/div/a/button',
                                           state="visible", timeout=30000)
                    page.click('//*[@id="site-content"]/div[2]/div/div/div[2]/div[1]/div/a/button')

                    # find_and_click(page,"Edit")
            print("等待页面加载完成")
            page.wait_for_selector("button:has-text('Markdown')", state="visible", timeout=120000)
            if not find_and_click(page, "Save Version"):
                print("Save Version通用点击方案失效，采用原始方案")
                save_version_buttons = [
                    '//*[@id="site-content"]/div[2]/div/div[1]/div/div/div[4]/div[1]/button',
                    '//*[@id="site-content"]/div[2]/div[2]/div/div[1]/div/div/div[4]/div[1]/button',
                    '//*[@id="site-content"]/div[3]/div/div[1]/div/div/div[4]/div[1]/button',
                    '//*[@id="site-content"]/div[2]/div/div[1]/div/div/div[4]/span[1]/div/button'
                ]
                time.sleep(7)
                if not save_version(page):
                    for save_version_button in save_version_buttons:
                        try:
                            page.wait_for_selector(save_version_button, state="visible",
                                                   timeout=30000)  # 使用wait_for_selector替换is_visable
                            page.click(save_version_button)
                            print("已保存版本")
                            break
                        except Exception as e:
                            print(f"尝试点击 {save_version_button} 失败: 尝试使用其他xpath路径定位")

            time.sleep(8)
            confirm_buttions = [
                '//*[@id="kaggle-portal-root-global"]/div/div[3]/div/div/div[4]/div[2]/button[2]',
                '/html/body/div[2]/div[3]/div/div/div[4]/div[2]/button[2]'
                '//*[@id="kaggle-portal-root-global"]/div[2]/div[3]/div/div/div[4]/div[2]/button[2]',
                "//button[contains(., 'Save')]",  # 方案 2：利用文本内容
                "button:has-text('Save')",  # 方案4 利用文本内容
                "/html/body/div[contains(@class,'MuiDrawer-root') and contains(@class,'MuiDrawer-modal')]/div[contains(@class,'MuiDrawer-paper')]/div/div/div[last()]/div[last()]/button[last()]",
            ]

            if not save(page):
                for confirm_button in confirm_buttions:
                    try:
                        page.wait_for_selector(confirm_button, state="visible",
                                               timeout=30000)  # 使用wait_for_selector替换is_visable
                        page.click(confirm_button)
                        print("已确认运行")
                        break
                    except Exception as e:
                        print(f"尝试点击 {confirm_button} 失败: 尝试使用其他xpath路径定位")
            print("run")
            time.sleep(5)
            print("项目运行中...")
            page.goto("https://www.kaggle.com/", timeout=900000)  # 返回主页准备退出登录



    except Exception as e:
        print(f"\033[91m任务失败：{str(e)}，重新尝试\033[0m")
        if browser:
            try:
                browser.close()
            except Exception as e:
                print(f"{str(e)}")
        start_instance(email, password)
    finally:

        if browser:
            print("任务完成，浏览器将关闭")
            try:
                browser.close()
            except Exception as e:
                print(f"{str(e)}")


def find_and_click(page, text, timeout=30000):
    """
    在页面中查找任意包含指定文本的元素并点击。
    """

    strategies = [
        lambda: page.get_by_role("button", name=text),
        lambda: page.get_by_title(text),
        lambda: page.get_by_label(text),
        lambda: page.locator(f"//button[@title='{text}']"),
        lambda: page.locator(f"//button[text()='{text}']"),
        lambda: page.locator(f"text=\"{text}\""),
        lambda: page.locator(f"//*[contains(text(), '{text}')]"),  # 通用查找
    ]

    for strategy in strategies:
        try:
            locator = strategy()
            if locator.count() == 0:
                continue
            locator.first.click(timeout=timeout)
            print(f"已点击包含文本 “{text}” 的元素")
            return True
        except PlaywrightTimeoutError:
            print(f"error：无法点击包含文本 “{text}” {e}")
            continue
        except Exception as e:
            continue

    print(f"❌ 无法点击文本 “{text}”，未找到匹配元素")
    return False


def save_version(page):
    try:
        # 推荐方法：使用 get_by_role 和 title
        page.get_by_role("button", name="Save Version").click(timeout=30000)
        print("已点击 Save Version 按钮 (使用 get_by_role 和 title)")
        return True
    except Exception as e:
        print(f"点击 Save Version 按钮失败: {e}")
        # 其他备选方案 (可选)
        try:
            page.get_by_title("Save Version").click(timeout=30000)
            print("已点击 Save Version 按钮 (使用 get_by_title)")
            return True
        except Exception as e:
            print(f"点击 Save Version 按钮失败: {e}")

        try:
            page.get_by_label("Save Version").click(timeout=30000)
            print("已点击 Save Version 按钮 (使用 get_by_label)")
            return True
        except Exception as e:
            print(f"点击 Save Version 按钮失败: {e}")

        try:
            page.locator("//button[@title='Save Version']").click(timeout=30000)
            print("已点击 Save Version 按钮 (使用 XPath)")
            return True
        except Exception as e:
            print(f"点击 Save Version 按钮失败: {e}")
        return False


def save(page):
    try:
        # 推荐方法：使用 get_by_role 和 name
        page.get_by_role("button", name="Save").click(timeout=30000)
        print("已点击 Save 按钮 (使用 get_by_role 和 name)")
        return True
    except Exception as e:
        print(f"点击 Save 按钮失败: {e}")

        # 其他备选方案 (可选)
        try:
            page.get_by_text("Save").click()
            print("已点击 Save 按钮 (使用 get_by_text)")
            return True
        except Exception as e:
            print(f"点击 Save 按钮失败: {e}")

        try:
            page.locator("button:has-text('Save')").click(timeout=30000)
            print("已点击 Save 按钮 (使用 CSS 选择器)")
            return True
        except Exception as e:
            print(f"点击 Save 按钮失败: {e}")

        try:
            page.locator("//button[contains(., 'Save')]").click(timeout=30000)
            print("已点击 Save 按钮 (使用 XPath)")
            return True
        except Exception as e:
            print(f"点击 Save 按钮失败: {e}")
        return False


def main():
    try:
        index = 0
        accounts = data['kaggle_accounts']
        print(len(accounts))
        print("========== 启动完成 ==========")
        print("项目地址：https://github.com/avilliai/Achernar  点个star喵，点个star谢谢喵")
        while True:
            email, password = accounts[index]['email'], accounts[index]['password']
            print(f"========== 开始第 {index} 次运行，使用账户：{email} ==========")

            start_instance(email, password)
            # kill_instance(email, password)
            # 可选：在两次运行之间添加延时，避免过快执行
            time.sleep(data['kaggle_change_account_interval'])
            # kill_instance(email, password)
            index += 1
            if index >= len(accounts):
                index = 0

    except Exception as e:
        print("\033[91m任务中断：" + str(e) + "\033[0m")


def cpolar_main():
    global tunnel_url
    login_url = "https://dashboard.cpolar.com/login"
    info_url = "https://dashboard.cpolar.com/status"
    credentials = {
        'login': data["cpolar"]["email"],
        'password': data["cpolar"]["password"]
    }

    # 创建一个 Session 对象，避免每次请求都重新登录
    session = requests.Session()

    def login(session, login_url, credentials):
        """ 登录函数，返回是否登录成功 """
        try:
            login_page = session.get(login_url)
            login_page_soup = BeautifulSoup(login_page.text, 'html.parser')

            csrf_token = login_page_soup.find('input', {'name': 'csrf_token'})['value']
            credentials['csrf_token'] = csrf_token

            login_response = session.post(login_url, data=credentials)

            if login_response.url == login_url:
                print("登录失败，请检查您的凭据。")
                return False
            else:
                print("登录成功。")
                return True
        except Exception as e:
            print(f"登录失败：{str(e)}")
            return False

    def fetch_info_from_website(session, info_url):
        """ 获取隧道信息，返回最新的 tunnel_url """
        try:
            response = session.get(info_url)
            response.raise_for_status()

            if response.status_code == 200:
                tunnels = []
                soup = BeautifulSoup(response.text, 'html.parser')
                table_rows = soup.select("table tbody tr")
                row = table_rows[-1] if table_rows else None
                if row:
                    columns = row.find_all("td")
                    if len(columns) > 0:
                        url_column = row.find("a")
                        newurl = url_column['href'] if url_column else "N/A"
                        tunnels.append(newurl.replace("http://", "https://"))

                try:
                    row = table_rows[-3] if table_rows else None
                    if row:
                        columns = row.find_all("td")
                        if len(columns) > 0:
                            url_column = row.find("a")
                            newurl = url_column['href'] if url_column else "N/A"
                            tunnels.append(newurl)
                except Exception as e:
                    print(f"获取隧道信息2失败：{str(e)}")
                return tunnels
            return None
        except Exception as e:
            print(f"获取隧道信息失败：{str(e)}")
            return None

    login(session, login_url, credentials)

    while True:
        # 定时刷新获取隧道 URL
        new_tunnel_url = fetch_info_from_website(session, info_url)

        if new_tunnel_url != None and new_tunnel_url != []:
            tunnel_url = new_tunnel_url
            print(f"最新隧道信息: {tunnel_url}")
        else:
            print("获取隧道信息失败，重新登录中...")
            # 如果获取链接失败，重新登录
            if not login(session, login_url, credentials):
                print("无法重新登录。")
                time.sleep(data['cpolar_check_interval'])
                continue
            new_tunnel_url = fetch_info_from_website(session, info_url)
            if new_tunnel_url != [] and new_tunnel_url != None:
                tunnel_url = new_tunnel_url
                print(f"最新隧道信息: {tunnel_url}")

        # 等待一段时间后再次获取
        time.sleep(data['cpolar_check_interval'])


def schedule_cpolar_main():  # cpolar定时任务
    cpolar_main()


def get_dynamic_ip():
    global tunnel_url
    get_ip_url = data["get_dynamic_ip"]["url"]

    def fetch_info_from_website():
        """ 获取隧道信息，返回最新的 tunnel_url """
        try:
            response = requests.get(get_ip_url)
            ip_address = response.text
            tunnels = [f"https://{ip_address}:{data['get_dynamic_ip']['port1']}",
                       f"https://{ip_address}:{data['get_dynamic_ip']['port2']}"]
            return tunnels
        except Exception as e:
            print(f"获取隧道信息失败：{str(e)}")
            return None

    while True:
        # 定时刷新获取隧道 URL
        new_tunnel_url = fetch_info_from_website()

        if new_tunnel_url != None and new_tunnel_url != []:
            tunnel_url = new_tunnel_url
            print(f"最新隧道信息: {tunnel_url}")
        else:
            print("获取隧道信息失败")
            new_tunnel_url = fetch_info_from_website()
            if new_tunnel_url != [] and new_tunnel_url != None:
                tunnel_url = new_tunnel_url
                print(f"最新隧道信息: {tunnel_url}")

        # 等待一段时间后再次获取
        time.sleep(data['cpolar_check_interval'])


@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def proxy_request(path):
    global tunnel_url, url_index
    if not tunnel_url:
        return jsonify({"error": "隧道地址未初始化，请稍后再试"}), 503

    print(f"收到外部请求：{request.method} {request.url}")

    try:
        # 获取请求数据
        if request.method == 'GET':
            external_request = request.args.to_dict()
        else:
            external_request = request.get_json()
        if len(tunnel_url) == 1:
            url_index = 0

        current_url = tunnel_url[url_index]
        url_index = (url_index + 1) % len(tunnel_url)

        modified_tunnel_url = f"{current_url}/{path}"
        if request.query_string:
            modified_tunnel_url += f"?{request.query_string.decode('utf-8')}"

        print(f"转发至新的隧道地址：{modified_tunnel_url}")
        if data['quest_proxy'] is not None and data['quest_proxy'] != '':
            proxy = data['quest_proxy']
            proxies = {"http": proxy, "https": proxy}
        else:
            proxies = None
        # 转发请求
        # 不要设置 Content-Type, 让 requests 自动处理
        headers = {key: value for key, value in request.headers.items() if key.lower() != 'host'}

        response = requests.request(request.method, modified_tunnel_url,
                                    params=request.args if request.method == 'GET' else None,
                                    json=external_request if request.method in ['POST', 'PUT', 'PATCH'] else None,
                                    data=request.get_data() if request.method not in ['GET', 'POST', 'PUT',
                                                                                      'PATCH'] else None,
                                    headers=headers, stream=True, proxies=proxies)

        print(f"转发请求完成，响应状态码：{response.status_code}")
        # 打印原始响应头
        print(f"原始响应头：{response.headers}")

        # 直接传递原始响应内容和头部给客户端
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk

        # 移除可能会导致问题的头部
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in response.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(generate(), response.status_code, headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if data["enable_cpolar_extension"]:
        threading.Thread(target=schedule_cpolar_main, daemon=True).start()
    if data["enable_kaggle_extension"]:
        threading.Thread(target=main, daemon=True).start()
    if data["enable_get_dynamic_ip"]:
        threading.Thread(target=get_dynamic_ip, daemon=True).start()

    app.run(host='0.0.0.0', port=data['port'])