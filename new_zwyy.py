#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.
import base64
import json
import os
import threading
import time

import ddddocr
import jsonpath
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

jsonfile = './zwyy_json.json'  # Json位置
times = int(time.time() * 1000)
tomorrow_date = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))
zwyy_con = requests.Session()

headers = {
    "Accept": "application/json, text/plain, */*",
    "Host": "zwyy.cidp.edu.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/92.0.4515.159 Safari/537.36"
}


# 加载Json
def load_zwyy_json():
    if not os.path.isfile(jsonfile):
        print('未找到zwyy_json.json，请检查！')
        return "JsonNotFile"
    zwyy_json = json.load(open(jsonfile, 'r'))  # 使用cron运行请写完整路径
    global zwyy_user, zwyy_time, zwyy_roomid, zwyy_devid, zwyy_devname, zwyy_priorityid, zwyy_priorityname, pushkey
    zwyy_user = jsonpath.jsonpath(zwyy_json, '$..user')[0]
    zwyy_time = jsonpath.jsonpath(zwyy_json, '$..time')[0]
    zwyy_roomid = jsonpath.jsonpath(zwyy_json, '$..roomid')
    zwyy_devid = jsonpath.jsonpath(zwyy_json, '$..devid')
    zwyy_devname = jsonpath.jsonpath(zwyy_json, '$..devname')
    zwyy_priorityid = (jsonpath.jsonpath(zwyy_user[0], '$..priority_id'))[0]
    zwyy_priorityname = (jsonpath.jsonpath(zwyy_user[0], '$..priority_name'))[0]
    pushkey = jsonpath.jsonpath(zwyy_json, '$..pushkey')[0]


# 推送&显示返回
def _push(text):
    print(text)
    try:
        push_url = f"https://api2.pushdeer.com/message/push?pushkey={pushkey}&text={text}"
        requests.get(push_url, timeout=3, verify=False)
    except:
        with open('./zwyy.log', 'a+') as f:
            print(text, file=f)


# 获取和拼凑密钥，返回密钥和随机码
def get_nonceStr_publicKey():
    url_nonceStr_publicKey = "https://zwyy.cidp.edu.cn/ic-web/login/publicKey"
    con_nonceStr_publicKey = zwyy_con.get(url_nonceStr_publicKey, verify=False)
    publicKey = '-----BEGIN PUBLIC KEY-----\n' + jsonpath.jsonpath(con_nonceStr_publicKey.json(), '$..publicKey')[
        0] + '\n-----END PUBLIC KEY-----'
    nonceStr = jsonpath.jsonpath(con_nonceStr_publicKey.json(), '$..nonceStr')[0]
    return publicKey, nonceStr


# RSA加密密码，返回密文
def encrypt_password(password):
    publicKey, nonceStr = get_nonceStr_publicKey()
    rsaKey = RSA.importKey(publicKey)
    cipher = PKCS1_v1_5.new(rsaKey)
    r = str(password) + ";" + nonceStr
    encrypt_text = (base64.b64encode(cipher.encrypt(r.encode(encoding="utf-8")))).decode('utf-8')
    return encrypt_text


# 获取和解析验证码，返回验证码文本
def get_captcha():
    ocr = ddddocr.DdddOcr(show_ad=False)  # 初始化ocr
    url_get_captcha = f"https://zwyy.cidp.edu.cn/ic-web/captcha?id={times}"
    con_get_captcha = zwyy_con.get(url_get_captcha, verify=False, headers=headers)
    captcha = ocr.classification(con_get_captcha.content)
    return captcha


# 登录，返回用户id和姓名
def get_login(userid, password):
    n = 0
    while n <= 8:
        captcha = get_captcha()
        pwd = encrypt_password(password)
        url_login = "https://zwyy.cidp.edu.cn/ic-web/login/user"
        data = {"logonName": userid,
                "password": pwd,
                "captcha": captcha,
                "consoleType": 16}
        con_login = zwyy_con.post(url_login, json=data, verify=False, headers=headers)
        if "登录成功" in con_login.text:
            accNo = jsonpath.jsonpath(con_login.json(), '$..accNo')[0]
            trueName = jsonpath.jsonpath(con_login.json(), '$..trueName')[0]
            return accNo, trueName
            pass
        if "验证码错误" in con_login.text:
            n -= 1
        if "账号或密码不正确" in con_login.text:
            _push(f"{userid}，账号或密码不正确")
            return int(00000000), int(00000000)
        if n == 8:
            return int(00000000), int(00000000)
        n += 1


# 获取指定时间BeginTime-EndTime单个座位
def get_a_resv(resvMember, resvDev, start_time, end_time, userid, password):
    BeginTime = tomorrow_date + " " + start_time  # 2022-11-01 13:05:00
    EndTime = tomorrow_date + " " + end_time  # 2022-11-01 14:50:00
    data = {"sysKind": 8, "appAccNo": int(resvMember), "memberKind": 1, "resvMember": [int(resvMember)],
            "resvBeginTime": BeginTime, "resvEndTime": EndTime, "testName": "", "captcha": "",
            "resvProperty": 0, "resvDev": [int(resvDev)], "memo": ""}
    con_nonceStr_publicKey = zwyy_con.post("https://zwyy.cidp.edu.cn/ic-web/reserve", json=data, verify=False,
                                           headers=headers)
    if "新增成功" in con_nonceStr_publicKey.text:
        return "新增成功"
    if "用户未登录" in con_nonceStr_publicKey.text:
        while 1:
            res = get_login(userid, password)
            if res == int(00000000):
                return "Error"


# 获取指定时间BeginTime-EndTime内单个教室座位,返回两组数据
def get_all_resv(resvMember, room_no, start_time, end_time, userid, password):
    dev_no = 0
    res_a = 00
    res_b = 00
    dev_id = zwyy_devid[room_no]
    dev_name = zwyy_devname[room_no]
    # 优选座位获取
    priority_res = get_a_resv(resvMember, zwyy_priorityid, start_time, end_time, userid, password)
    if priority_res == "新增成功":
        return zwyy_priorityid, zwyy_priorityname
    # 正常循环获取
    while dev_no < len(dev_id):
        if dev_id[dev_no] == zwyy_priorityid:
            dev_no += 1
            continue
        res = get_a_resv(resvMember, dev_id[dev_no], start_time, end_time, userid, password)
        dev_no += 1
        if res == "新增成功":
            return dev_id[dev_no], dev_name[dev_no]
        if res == "Error":
            break
    return res_a, res_b


# 循环time_no时间段内获取多个教室
def get_all_room(resvMember, time_no, name, userid, password):
    start_time = jsonpath.jsonpath(zwyy_time[time_no], '$..start_time')[0]
    end_time = jsonpath.jsonpath(zwyy_time[time_no], '$..end_time')[0]
    room_no = 0
    while room_no < len(zwyy_roomid):
        res_a, res_b = get_all_resv(resvMember, room_no, start_time, end_time, userid, password)
        if "TY" in str(res_b):
            res = f"姓名：{name}，预约成功，位置为{res_b}。时间段为{start_time}到{end_time}"
            _push(res)
            break
        room_no += 1
        if res_b == 00 and room_no >= len(zwyy_roomid):
            res = f"姓名：{name}，日期：{tomorrow_date}，{start_time}至{end_time}时间段预约座位失败 "
            _push(res)
            break


# 多线程获取多个时间段内的座位
def zwyy_th(resvMember, name, userid, password):
    time_thread = 0
    threads = []
    while time_thread < len(zwyy_time):
        t = threading.Thread(target=get_all_room, args=(resvMember, time_thread, name, userid, password,))
        threads.append(t)
        t.start()
        time_thread += 1
    for _ in threads:
        t.join()
    return "OK"


def v_info():
    logo_text = "                                                          \n" \
                "██╗██████╗ ██████╗    ███████╗██╗    ██╗██╗   ██╗██╗   ██╗\n" \
                "██║██╔══██╗██╔══██╗   ╚══███╔╝██║    ██║╚██╗ ██╔╝╚██╗ ██╔╝\n" \
                "██║██║  ██║██████╔╝     ███╔╝ ██║ █╗ ██║ ╚████╔╝  ╚████╔╝ \n" \
                "██║██║  ██║██╔═══╝     ███╔╝  ██║███╗██║  ╚██╔╝    ╚██╔╝  \n" \
                "██║██████╔╝██║███████╗███████╗╚███╔███╔╝   ██║      ██║   \n" \
                "╚═╝╚═════╝ ╚═╝╚══════╝╚══════╝ ╚══╝╚══╝    ╚═╝      ╚═╝   \n" \
                "                                                          \n"
    update_text = "版本更新说明\n版本v1.0，基于新座位预约系统编写，基本功能正常使用，第一个发布版。\n版本v1.1，优化显示，独立部分模块，允许未到时间提前登录的，概率上加快抢座位速度。\n"
    print(logo_text + update_text)


def to_print(text):
    print('\r' + str(text), end='', flush=True)


def p_run():
    # 确认时间，提前一分钟进行登录
    now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    if now_time < 659:
        to_print("时间未到6:59，将不会进行登录，请等待时间到点，将每秒重新检查时间")
        while now_time < 659:
            to_print('现在时间是' + str(time.strftime('%H:%M:%S', time.localtime(time.time()))))
            time.sleep(1)
            now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    # 确认时间，进行登录
    to_print('进行登录……')
    user = (jsonpath.jsonpath(zwyy_user[0], '$..id'))[0]
    pwd = (jsonpath.jsonpath(zwyy_user[0], '$..pwd'))[0]
    userid, name = get_login(user, pwd)
    if userid == int(00000000):
        _push("登录出现问题，请检查！")
        return
    # 确认时间，到点抢座位
    now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    if now_time < 700:
        to_print("时间未到7:00，将不会进行座位预约，请等待时间到点，将每秒重新检查时间")
        while now_time < 700:
            to_print('现在时间是' + str(time.strftime('%H:%M:%S', time.localtime(time.time()))))
            time.sleep(1)
            now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    to_print('现在时间是' + str(time.strftime('%H:%M:%S', time.localtime(time.time()))) + ",开始预约座位！\n")
    res = zwyy_th(userid, name, userid, pwd)
    return res


def main():
    v_info()
    load_res = load_zwyy_json()  # 加载Json
    if load_res == "JsonNotFile":
        return
    res = p_run()
    if res == "OK":
        os.system("pause")


main()
