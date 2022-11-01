#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.
import base64
import json
import threading
import time

import ddddocr
import jsonpath
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

# 加载json文件，目前仅支持单用户
zwyy_json = json.load(open('./zwyy_json.json', 'r', encoding='utf-8'))  # 使用cron运行请写完整路径
zwyy_user = jsonpath.jsonpath(zwyy_json, '$..user')[0]
zwyy_time = jsonpath.jsonpath(zwyy_json, '$..time')[0]
zwyy_roomid = jsonpath.jsonpath(zwyy_json, '$..roomid')
zwyy_devid = jsonpath.jsonpath(zwyy_json, '$..devid')
zwyy_devname = jsonpath.jsonpath(zwyy_json, '$..devname')
zwyy_priorityid = (jsonpath.jsonpath(zwyy_user[0], '$..priority_id'))[0]
zwyy_priorityname = (jsonpath.jsonpath(zwyy_user[0], '$..priority_name'))[0]
pushkey = jsonpath.jsonpath(zwyy_json, '$..pushkey')[0]

times = int(time.time() * 1000)
zwyy_day = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))
zwyy_con = requests.Session()
ocr = ddddocr.DdddOcr()

headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/92.0.4515.159 Safari/537.36",
}


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
        print(con_login.json())
        if "登录成功" in con_login.text:
            accNo = jsonpath.jsonpath(con_login.json(), '$..accNo')[0]
            trueName = jsonpath.jsonpath(con_login.json(), '$..trueName')[0]
            return accNo, trueName
            pass
        if "验证码错误" in con_login.text:
            n -= 1
        if n == 8:
            return int(00000000), int(00000000)
        n += 1


# 获取指定时间BeginTime-EndTime单个座位
def get_a_resv(resvMember, resvDev, start_time, end_time, userid, password):
    BeginTime = zwyy_day + " " + start_time  # 2022-11-01 13:05:00
    EndTime = zwyy_day + " " + end_time  # 2022-11-01 14:50:00
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
            res = f"姓名：{name}，日期：{zwyy_day}，{start_time}至{end_time}时间段预约座位失败 "
            _push(res)
            break


# 多线程获取多个时间段内的座位
def zwyy_th(resvMember, name, userid, password):
    time_thread = 0
    while time_thread < len(zwyy_time):
        threading.Thread(target=get_all_room, args=(resvMember, time_thread, name, userid, password,)).start()
        time_thread += 1


def main():
    # 确认时间，到点才运行之后的部分
    now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    while now_time < 700:
        print("时间未到，请等待时间到点，将于1秒后重新检查时间")
        time.sleep(1)
        now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    # 正式运行部分
    user = (jsonpath.jsonpath(zwyy_user[0], '$..id'))[0]
    pwd = (jsonpath.jsonpath(zwyy_user[0], '$..pwd'))[0]
    userid, name = get_login(user, pwd)
    if userid == int(00000000):
        _push("登录出现问题，请检查！")
        return
    zwyy_th(userid, name, userid, pwd)


main()
